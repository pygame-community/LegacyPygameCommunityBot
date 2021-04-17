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
import numpy
import pygame_gui

import discord
import pkg_resources
import pygame
import pygame._sdl2
import pygame.gfxdraw

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

pkgs = sorted(i.key for i in pkg_resources.working_set)

for module in pkgs:
    try:
        doc_module_dict[module] = __import__(module.replace("-", "_"))
    except BaseException:
        pass


def get(name):
    """
    Helper function to get docs
    """
    splits = name.split(".")

    try:
        is_builtin = bool(getattr(builtins, splits[0]))
    except AttributeError:
        is_builtin = False

    if splits[0] not in doc_module_dict and not is_builtin:
        return "Unknown module!", "No such module is available for its documentation."

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

    allowed_obj_names = {
        "module": [],
        "type": [],
        "function": [],
        "method_descriptor": [],
        "builtin_function_or_method": [],
    }

    formatted_allowed_obj_names = {
        "module": "Modules",
        "type": "Types",
        "function": "Functions",
        "method_descriptor": "Methods",
        "builtin_function_or_method": "Built-in Functions Or Methods",

    }

    for i in module_objs:
        obj_type_name = type(module_objs[i]).__name__
        if i.startswith("__") or obj_type_name not in allowed_obj_names:
            continue

        allowed_obj_names[obj_type_name].append(i)

    footer = ""
    for k in allowed_obj_names:
        obj_name_list = allowed_obj_names[k]

        if not obj_name_list:
            continue

        sub_name = f"**{formatted_allowed_obj_names[k]}**\n"
        sub_values = util.code_block('\n'.join(allowed_obj_names[k]))
        footer += f"{sub_name}{sub_values}"

    docs = util.code_block(obj.__doc__, 2048 - len(header) - len(footer))
    return f"Documentation for `{name}`", header + docs + footer
