"""Allow ``python -m herds.daemon`` to run the agent (used by ``herds host``)."""

from . import main

if __name__ == "__main__":
    main()
