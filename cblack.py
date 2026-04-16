#!/usr/bin/python3
# -*- coding: utf-8 -*-
import re
import sys

__version__ = "26.3.1"

import sys
from os.path import isdir

import importlib
import importlib.util
import importlib.machinery


_real_pathfinder = sys.meta_path[-1]


class CBlackModuleLoader(type(_real_pathfinder)):
  """
  This custom module loader is used in order to prevent black to load a
  dynamic library as the module, and load the python module instead.

  This is done for the later black monkeypatching to work. Otherwise binaries
  cannot be patched.

  Please note that this should not prevent other libraries from loading their
  dynamic library modules. So everything will load as expected but black module.

  Reference:
    https://stupidpythonideas.blogspot.com/2015/06/hacking-python-without-hacking-python.html
  """

  # all "black" folders contain the substring "/black-<version>"
  # (e.g. "/usr/local/lib/python3.14/site-packages/black-26.3.1-py3.14-linux-x86_64.egg")
  # (e.g. "/opt/local/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/black")
  _black_folder = "/black-%s" % __version__

  # local installation of black folder don't necessarily need to contain the
  # version, so the path includes '/black/'
  _black_local_folder = "/black/"

  @classmethod
  def find_spec(cls, fullname, path=None, target=None):
    spec = _real_pathfinder.find_spec(fullname, path, target)
    if (
      spec
      and spec.origin
      and (
        (CBlackModuleLoader._black_folder in spec.origin)
        or (CBlackModuleLoader._black_local_folder in spec.origin)
      )
      and spec.origin.endswith(".so")
    ):
      # replace known dynamic loader module extensions by their "py" counterpart
      location = spec.origin
      for ext in importlib.machinery.EXTENSION_SUFFIXES:
        if location.endswith(ext):
          location = location.replace(ext, ".py")
          break

      # load & replace the spec from the python file
      spec = importlib.util.spec_from_file_location(spec.name, location)

    return spec


# Replace the real module loader by our own
sys.meta_path[-1] = CBlackModuleLoader

try:
  import black.strings as black_str
  import black.linegen as black_line
  from black import main as black_main
except ImportError:
  print(f"Cannot import black. Have you installed black v{__version__}?")

# Save original methods
_orig_line_str = black_line.Line.__str__
from black.strings import fix_multiline_docstring as _orig_fix_docstring

# Patch for 2-space indentation
def line_str_indent_two_spaces(self) -> str:
  original = _orig_line_str(self)
  if not original.startswith(" "):
    return original

  noLeftSpaces = original.lstrip(" ")
  nLeadingSpaces = len(original) - len(noLeftSpaces)

  # reindent by generating half the spaces (from 4-space blocks to 2-space blocks)
  return " " * (nLeadingSpaces >> 1) + noLeftSpaces


def patched_fix_docstring(docstring: str, prefix: str) -> str:
  """Indent doc strings by 2 spaces instead of 4"""
  return _orig_fix_docstring(docstring, " " * (len(prefix) >> 1))


# Apply monkeypatches
black_line.Line.__str__ = line_str_indent_two_spaces
black_line.fix_multiline_docstring = patched_fix_docstring
black_str.fix_multiline_docstring = patched_fix_docstring


def main():
  # behave like normal black code
  sys.argv[0] = re.sub(r"(-script\.pyw?|\.exe)?$", "", sys.argv[0])
  sys.exit(black_main())


if __name__ == "__main__":
  sys.exit(main())
