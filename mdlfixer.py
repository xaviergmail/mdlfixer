import argparse

import os
import shutil
import sys
import struct

args = None

# struct.unpack definitions
# Translated from studio.h
# https://github.com/ValveSoftware/source-sdk-2013/blob/0d8dceea4310fde5706b3ce1c70609d72a38efdf/mp/src/public/studio.h

# Offset to 2nd file length in studiohdr_t
STUDIOHDR_LEN_OFF = 12 + 64

studiohdr_t = (
    "<"     # Little endian
    "12x"   # id, version, checksum. Unwanted.
    "64s"   # legacy model name
    "i"     # file length in bytes
    "320x"  # unwanted stuff
    "i"     # studiohdr2_t pointer
)

# studohdr2_t would be '<20xi' but all we need is an int
STUDIOHDR2_NAME_OFF = 20
leint_t = "<i"

# Old MDL files have a hardcoded 64-byte name rather
# than a null-terminated string.
NAME_OFF = 0x0C
NAME_LEN = 64


def check_file(searchdir, fname):
    needs_fixing = False
    errs = []

    with open(fname, "rb") as f:
        size = struct.calcsize(studiohdr_t)
        studiohdr = struct.unpack(studiohdr_t, f.read(size))

        model_name_legacy = studiohdr[0].partition(b"\0")[0].decode("ascii")
        model_name_legacy = model_name_legacy.replace("\\", "/").lower()

        actual_fname = fname[len(searchdir)+1:].lower()

        file_len = studiohdr[1]

        studiohdr2_pointer = studiohdr[2]
        is_legacy = studiohdr2_pointer == 0

        model_name = model_name_legacy

        if len(actual_fname) > NAME_LEN:
            severity = "WARN" if is_legacy else "FATAL"
            errs.append(f"{severity}: {fname} path is >{NAME_LEN} characters!")

            if is_legacy:
                # We would overflow in the rest of the header if we tried.
                return errs

        if not is_legacy:
            size = struct.calcsize(leint_t)

            f.seek(studiohdr2_pointer + STUDIOHDR2_NAME_OFF)
            szname_pointer = struct.unpack(leint_t, f.read(size))[0]

            if szname_pointer == 0:
                is_legacy = False

            else:
                f.seek(studiohdr2_pointer + szname_pointer)

                buf = b""
                while True:
                    chunk = 64
                    read = f.read(chunk)

                    partitioned = read.partition(b"\0")
                    buf += partitioned[0]

                    if len(read) < chunk or partitioned[1] == b"\0":
                        break

                model_name = buf.decode("utf-8")

        if actual_fname != model_name:
            needs_fixing = args.fix
            errstr = f"Found with filesystem path {actual_fname} " \
                     f"but mdl path {model_name}"

            if needs_fixing:
                print(errstr)
            else:
                errs.append(errstr)

    # Let previous context manager close the file before making backup
    if needs_fixing:
        if args.backup:
            backed = fname + ".bak"
            print("Backing up old file to ", backed)
            shutil.copyfile(fname, backed)

        print("Fixing...")
        bname = actual_fname.encode("utf-8") + b"\0"
        bname_legacy = bname[:NAME_LEN] + (b"\0" * (NAME_LEN - len(bname)))

        assert len(bname_legacy) == NAME_LEN

        with open(fname, "r+b") as f:
            f.seek(NAME_OFF)
            f.write(bname_legacy)

            if not is_legacy:
                # We will write the new model at the end of the file
                # to avoid breaking all of the other binary offsets.

                # Update the studiohdr2's szName pointer to end of file
                f.seek(studiohdr2_pointer + STUDIOHDR2_NAME_OFF)
                f.write(struct.pack(leint_t, file_len - studiohdr2_pointer))

                # Write the new name
                f.seek(file_len)
                f.write(bname)

                # Update the builtin file length in studiohdr
                new_len = file_len + len(bname)
                f.seek(STUDIOHDR_LEN_OFF)
                f.write(struct.pack(leint_t, new_len))

    return errs


def main():
    found_errors = []
    searchdir = os.path.abspath(args.dir)

    for root, _, files in os.walk(searchdir):
        for fname in files:
            if os.path.splitext(fname)[1] == ".mdl":
                full_path = os.path.join(root, fname)
                errs = check_file(searchdir, full_path)

                if errs and len(errs) > 0:
                    found_errors += errs

    if len(found_errors) > 0:
        print("Found the following errors while parsing files:\n\n")
        for fname in found_errors:
            print(fname)

        if args.error:
            sys.exit(1)


if __name__ == "__main__":
    desc = """MDLFixer - Fixes hardcoded model paths in .mdl files
    for models that were innocently moved after being compiled."""

    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument("dir", type=str, default=os.getcwd(), nargs="?",
                        help="Directory to process mdl files in. "
                             "Must be the game or addon's 'models' folder.")

    parser.add_argument("-f", "--fix", default=False, action="store_true",
                        help="Attempt to fix malformed files in-place")

    parser.add_argument("-e", "--error", default=False, action="store_true",
                        help="Returns a non-zero return code if "
                             "malformed models are found. Useful for CI.")

    parser.add_argument("-b", "--backup", default=False, action="store_true",
                        help="Copy original files to <filename.mdl>.bak "
                             "before attempting to apply an in-place fix "
                             "(Requires --fix)")

    args = parser.parse_args()

    main()

