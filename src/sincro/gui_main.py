import runpy
import sys
from multiprocessing import freeze_support



PYSPARK_WORKER_MODULES = {"pyspark.daemon", "pyspark.worker"}


def requested_pyspark_module(arguments: list[str]) -> str | None:
    """Identifica quando o Java reinicia o executável como Python worker."""
    if len(arguments) >= 3 and arguments[1] == "-m":
        module = arguments[2]
        if module in PYSPARK_WORKER_MODULES:
            return module
    return None


def main() -> int:
    """Abre a GUI ou atende ao processo worker solicitado pelo Spark."""
    freeze_support()
    module = requested_pyspark_module(sys.argv)
    if module:
        sys.argv = sys.argv[2:]
        runpy.run_module(module, run_name="__main__")
        return 0
    from sincro.desktop.app import main as desktop_main
    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())


# @hugaojanuario
