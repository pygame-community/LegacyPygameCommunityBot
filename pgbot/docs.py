import asyncio
import builtins
import collections
import importlib
import itertools
import json
import math
import os
import pickle
import random
import re
import socket
import string
import sys
import threading
import time
import timeit


import discord
import pkg_resources
import pygame
import pygame._sdl2
import pygame.gfxdraw

from . import common

doc_modules = {  # Modules to provide documentation for
    "pygame": pygame,
    "discord": discord,
    "asyncio": asyncio,
    "json": json,
    "sys": sys,
    "os": os,
    "socket": socket,
    "random": random,
    "re": re,
    "math": math,
    "pickle": pickle,
    "threading": threading,
    "time": time,
    "timeit": timeit,
    "string": string,
    "itertools": itertools,
    "builtins": builtins,
    "gc": gc,
    "pickle": pickle,
    "collections": collections,
    "discord": discord,

}

for module in sys.modules:
    doc_modules[module] = sys.modules[module]

pkgs = sorted(i.key for i in pkg_resources.working_set)

for module in pkgs:
    try:
        doc_modules[module] = __import__(module.replace("-", "_"))
    except BaseException:
        pass


def get(name):
    """
    Helper function to get docs
    """
    splits = name.split(".")

    if splits[0] not in doc_modules:
        return "Unknown module!", "No such module is available for its documentation."

    objects = doc_modules
    obj = None

    for part in splits:
        try:
            obj = objects[part]
            try:
                objects = vars(obj)
            except BaseException:  # TODO: Figure out proper exception
                objects = {}
        except KeyError:
            return (
                "Class/function/sub-module not found!", 
                f"There's no such thing here named `{name}`"
            )

    messg = str(obj.__doc__).replace("```", common.ESC_CODE_BLOCK_QUOTE)

    if len(messg) + 11 > 2048:
        return f"Documentation for {name}", "```\n" + messg[:2037] + " ...```"

    messg = "```\n" + messg + "```\n\n"

    if splits[0] == "pygame":
        doclink = "https://www.pygame.org/docs"
        if len(splits) > 1:
            doclink += "/ref/" + splits[1].lower() + ".html"
            doclink += "#"
            doclink += "".join([s + "." for s in splits])[:-1]
        messg = "Online documentation: " + doclink + "\n" + messg

    allowed_obj_names = {
        "module",
        "type",
        "function",
        "method_descriptor",
        "builtin_function_or_method"
    }

    for obj in objects:
        if obj.startswith("__"):
            continue
        if type(objects[obj]).__name__ not in allowed_obj_names:
            continue
        messg += "**" + type(objects[obj]).__name__.upper() + "** `" + obj + "`\n"

    if len(messg) > 2048:
        return f"Documentation for {name}", messg[:2044] + " ..."
    else:
        return f"Documentation for {name}", messg
