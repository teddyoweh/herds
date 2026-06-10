"""Allow ``python -m darwin.daemon`` to run the agent (used by ``darwin host``)."""

from . import main

if __name__ == "__main__":
    main()
