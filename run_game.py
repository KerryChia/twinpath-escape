import sys

from core.localization import t

MIN_VER = (3, 12)

if sys.version_info[:2] < MIN_VER:
    sys.exit(t("app.python_version_error", major=MIN_VER[0], minor=MIN_VER[1]))

from main import main  # noqa: E402

main()
