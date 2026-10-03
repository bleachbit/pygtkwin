"""Check the built Python for known miscompilations."""

import sys


class List(list):
    pass


def main():
    # Linked with /OPT:ICF, this ran list concatenation on the int and
    # crashed instead of raising TypeError
    try:
        _ = 1 + List()
    except TypeError:
        return
    sys.exit("1 + List() did not raise TypeError")


if __name__ == "__main__":
    main()
