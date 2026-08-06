from typing import Final, NamedTuple

__all__ = ("__version__", "__version_info__")


class Version(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int

    def _rl_shorthand(self) -> str:
        return {
            "alpha": "a",
            "beta": "b",
            "candidate": "rc",
        }[self.releaselevel]

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.micro}"
        if self.releaselevel != "final":
            version = f"{version}{self._rl_shorthand()}{self.serial}"
        return version


__version_info__: Final[Version] = Version(
    major=0, minor=2, micro=1, releaselevel="final", serial=0
)
__version__: Final[str] = str(__version_info__)
