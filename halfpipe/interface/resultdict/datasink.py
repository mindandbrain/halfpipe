# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
from os import path as op
from pathlib import Path
import logging
from shutil import copyfile
from inflection import camelize
import hashlib
import json
import re

from nipype.interfaces.base import traits, TraitedSpec, SimpleInterface

from ...io import DictListFile
from ...model import FuncTagsSchema, ResultdictSchema, entities
from ...utils import splitext, findpaths, first, formatlikebids
from ...resource import get as getresource


def _make_path(sourcefile, type, tags, suffix, **kwargs):
    path = Path()

    assert type in ["report", "image"]

    for entity in ["sub", "ses"]:
        tagval = tags.get(entity)
        if tagval is not None:
            path = path.joinpath(f"{entity}-{tagval}")

    if type == "image":
        path = path.joinpath(f"func")

    if type == "report":
        path = path.joinpath(f"figures")

    _, ext = splitext(sourcefile)
    filename = f"{suffix}{ext}"  # keep original extension
    kwtags = list(kwargs.items())
    for tagname, tagval in reversed(kwtags):  # reverse because we are prepending
        if tagval is not None:
            tagval = formatlikebids(tagval)
            filename = f"{tagname}-{tagval}_{filename}"
    for entity in entities:  # is already reversed
        tagval = tags.get(entity)
        if tagval is not None:
            filename = f"{entity}-{tagval}_{filename}"

    return path / filename


def _copy_file(inpath, outpath):
    outpath.parent.mkdir(exist_ok=True, parents=True)
    if outpath.exists():
        if os.stat(inpath).st_mtime > os.stat(outpath).st_mtime:
            logging.getLogger("halfpipe").debug(f'Not overwriting file "{outpath}"')
            return
        logging.getLogger("halfpipe").info(f'Overwriting file "{outpath}"')
    copyfile(inpath, outpath)


def _find_sources(inpath):
    hash = None
    inputpaths = None
    for parent in Path(inpath).parents:
        hashfile = first(parent.glob("_0x*.json"))
        if hashfile is not None:
            match = re.match(r"_0x(?P<hash>[0-9a-f]{32})\.json", hashfile.name)
            if match is not None:
                hash = match.group("hash")
            with open(hashfile, "r") as fp:
                inputpaths = findpaths(json.load(fp))
                break
    return inputpaths, hash


def _format_metadata_value(obj):
    if not isinstance(obj, dict):
        return obj
    return {
        _format_metadata_key(k): _format_metadata_value(v)
        for k, v in obj.items()
    }


def _format_metadata_key(key):  # camelize
    if key == "ica_aroma":
        return "ICAAROMA"
    if key == "fwhm":
        return "FWHM"
    if key == "hp_width":
        return "HighPassWidth"
    if key == "lp_width":
        return "LowPassWidth"
    return camelize(key)


class ResultdictDatasinkInputSpec(TraitedSpec):
    base_directory = traits.Directory(
        desc="Path to the base directory for storing data.", mandatory=True
    )
    indicts = traits.List(traits.Dict(traits.Str(), traits.Any()))


class ResultdictDatasink(SimpleInterface):
    input_spec = ResultdictDatasinkInputSpec
    output_spec = TraitedSpec

    always_run = True

    def _run_interface(self, runtime):
        base_directory = Path(self.inputs.base_directory)

        resultdict_schema = ResultdictSchema()

        derivatives_directory = base_directory / "derivatives" / "halfpipe"
        reports_directory = base_directory / "reports"

        indexhtml_path = reports_directory / "index.html"
        _copy_file(getresource("index.html"), indexhtml_path)

        valdicts = []
        imgdicts = []
        preprocdicts = []

        for indict in self.inputs.indicts:
            resultdict = resultdict_schema.dump(indict)

            tags = resultdict["tags"]
            metadata = resultdict["metadata"]
            images = resultdict["images"]
            reports = resultdict["reports"]
            vals = resultdict["vals"]

            metadata = _format_metadata_value(metadata)

            # images

            for key, inpath in images.items():
                outpath = None
                if key in ["effect", "variance", "z", "dof"]:  # apply rule
                    outpath = derivatives_directory / _make_path(inpath, "image", tags, "statmap", stat=key)
                else:
                    outpath = derivatives_directory / _make_path(inpath, "image", tags, key)
                _copy_file(inpath, outpath)

                if key in ["effect", "reho", "falff", "alff", "bold"]:
                    stem, extension = splitext(outpath)
                    if extension in [".nii", ".nii.gz"]:
                        with open(outpath.parent / f"{stem}.json", "w") as fp:
                            fp.write(json.dumps(metadata, sort_keys=True, indent=4))

                        if key == "bold":
                            outdict = dict(**tags)
                            outdict.update({"status": "done"})
                            preprocdicts.append(outdict)

            # reports

            for key, inpath in reports.items():
                outpath = reports_directory / _make_path(inpath, "report", tags, key)
                _copy_file(inpath, outpath)

                hash = None
                sources = metadata.get("sources")

                if sources is None:
                    sources, hash = _find_sources(inpath)

                if hash is None:
                    md5 = hashlib.md5()
                    with open(inpath, "rb") as fp:
                        md5.update(fp.read())
                    hash = md5.hexdigest()

                outdict = dict(**tags)

                path = str(op.relpath(outpath, start=reports_directory))
                outdict.update({"desc": key, "path": path, "hash": hash})

                if sources is not None:
                    outdict["sourcefiles"] = []
                    for source in sources:
                        source = Path(source)
                        if base_directory in source.parents:
                            source = op.relpath(source, start=reports_directory)
                        outdict["sourcefiles"].append(str(source))

                imgdicts.append(outdict)

            # vals

            if len(vals) > 0:
                outdict = FuncTagsSchema().dump(tags)
                outdict.update(vals)
                valdicts.append(outdict)

        # dictlistfile updates

        if len(valdicts) > 0:
            valspath = reports_directory / "reportvals.js"
            valsfile = DictListFile.cached(valspath)
            with valsfile:
                for valdict in valdicts:
                    valsfile.put(valdict)
                valsfile.to_table()

        if len(imgdicts) > 0:
            imgspath = reports_directory / "reportimgs.js"
            imgsfile = DictListFile.cached(imgspath)
            with imgsfile:
                for imgdict in imgdicts:
                    imgsfile.put(imgdict)

        if len(preprocdicts) > 0:
            preprocpath = reports_directory / "reportpreproc.js"
            preprocfile = DictListFile.cached(preprocpath)
            with preprocfile:
                for preprocdict in preprocdicts:
                    preprocfile.put(preprocdict)
                preprocfile.to_table()

        return runtime
