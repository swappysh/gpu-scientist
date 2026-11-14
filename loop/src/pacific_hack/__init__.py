"""pacific-hack: self-improving forecaster loop on shared memory (Track 2 + past.dev side prize)."""


def main(argv=None) -> None:
    from .run import main as run_main  # lazy: keeps `python -m pacific_hack.run` warning-free

    run_main(argv)


__all__ = ["main"]
