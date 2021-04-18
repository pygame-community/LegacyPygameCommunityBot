import asyncio
import builtins
import cmath
import collections
import gc
import importlib
import itertools
import json
import math
import os
import pickle
import random
import re
import socket
import sqlite3
import string
import sys
import threading
import time
import timeit
import types

import discord
import numpy
import pkg_resources
import pygame
import pygame._sdl2
import pygame.gfxdraw
import pygame_gui

from . import common, util

doc_module_tuple = (
    asyncio,
    builtins,
    cmath,
    collections,
    discord,
    gc,
    itertools,
    json,
    math,
    numpy,
    os,
    pickle,
    pygame,
    pygame_gui,
    random,
    re,
    socket,
    sqlite3,
    string,
    sys,
    threading,
    time,
    timeit,
)
doc_module_dict = {}

for module_obj in doc_module_tuple:
    doc_module_dict[module_obj.__name__] = module_obj

for module in sys.modules:
    doc_module_dict[module] = sys.modules[module]


for module in pkg_resources.working_set:  # pylint: disable=not-an-iterable
    try:
        doc_module_dict[module] = __import__(module.replace("-", "_"))
    except BaseException:
        pass


async def put_main_doc(name, channel):
    """
    Put main part of the doc into embed(s)
    """
    splits = name.split(".")

    try:
        is_builtin = bool(getattr(builtins, splits[0]))
    except AttributeError:
        is_builtin = False

    if splits[0] not in doc_module_dict and not is_builtin:
        return "Unknown module!", "No such module was found."

    module_objs = dict(doc_module_dict)
    obj = None

    for part in splits:
        try:
            try:
                is_builtin = getattr(builtins, part)
            except AttributeError:
                is_builtin = None

            if is_builtin:
                obj = is_builtin
            else:
                obj = module_objs[part]

            try:
                module_objs = vars(obj)
            except TypeError:
                module_objs = {}
        except KeyError:
            return (
                "Class/function/sub-module not found!",
                f"There's no such thing here named `{name}`"
            )

    if isinstance(obj, (int, float, str, dict, list, tuple, bool)):
        return f"Documentation for {name}", \
            f"{name} is a constant with a type of `{obj.__class__.__name__}`" \
            " which does not have documentation."

    header = ""
    if splits[0] == "pygame":
        doclink = "https://www.pygame.org/docs"
        if len(splits) > 1:
            doclink += "/ref/" + splits[1].lower() + ".html"
            doclink += "#"
            doclink += "".join([s + "." for s in splits])[:-1]
        header = "Online documentation: " + doclink + "\n"

    docs = "" if obj.__doc__ is None else obj.__doc__

    lastchar = 0
    cnt = 0
    while len(docs) >= lastchar:
        cnt += 1
        if cnt >= common.DOC_EMBED_LIMIT:
            text = docs[lastchar:]
        else:
            text = docs[lastchar: lastchar + 2040]

            # Try to split docs into paragraphs. If that does not work, split
            # based on sentences. If that too does not work, then just split
            # blindly
            ind = text.rfind("\n\n")
            if ind > 1500:
                lastchar += ind
                text = text[:lastchar]
            else:
                ind = text.rfind("\n")
                if ind > 1500:
                    lastchar += ind
                    text = text[:lastchar]
                else:
                    lastchar += 2040

        await util.send_embed(
            channel,
            f"Documentation for `{name}`",
            header + util.code_block(text)
        )

        header = ""
        if cnt >= common.DOC_EMBED_LIMIT:
            break

    return module_objs, name


async def put_doc(name, channel):
    """
    Helper function to get docs
    """
    module_objs, name = await put_main_doc(name, channel)

    allowed_obj_names = {
        "Modules": [],
        "Types": [],
        "Functions": [],
        "Methods": [],
        "Functions/Methods": [],
    }

    formatted_obj_names = {
        "module": "Modules",
        "type": "Types",
        "function": "Functions",
        "method_descriptor": "Methods",
    }

    for oname, modmember in module_objs.items():
        if type(modmember).__name__ == "builtin_function_or_method":
            # Disambiguate into funtion or method
            obj_type_name = None
            if isinstance(modmember, types.BuiltinFunctionType):
                obj_type_name = "Functions"
            elif isinstance(modmember, types.BuiltinMethodType):
                obj_type_name = "Methods"
        else:
            obj_type_name = formatted_obj_names.get(type(modmember).__name__)

        if oname.startswith("__") or obj_type_name is None:
            continue

        allowed_obj_names[obj_type_name].append(oname)

    for otype, olist in allowed_obj_names.items():
        if not olist:
            continue

        await util.send_embed(
            channel,
            f"{otype} for `{name}`",
            util.code_block('\n'.join(olist))
        )
