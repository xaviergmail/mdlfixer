MDLFixer
===
Fixes hardcoded model paths in .mdl files for models that were innocently moved after being compiled.

Usage
====
`python3 mdlfixer.py --help`

```
python3 mdlfixer.py [-h] [-f] [-e] [-b] [dir]

positional arguments:
  dir           Directory to process mdl files in. Must be the game or addon's
                'models' folder.

optional arguments:
  -h, --help    show this help message and exit
  -f, --fix     Attempt to fix malformed files in-place
  -e, --error   Returns a non-zero return code if malformed models are found.
                Useful for CI.
  -b, --backup  Copy original files to <filename.mdl>.bak before attempting to
                apply an in-place fix (Requires --fix)

```
