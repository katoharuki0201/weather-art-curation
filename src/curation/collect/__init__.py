from .aic import collect_aic
from .cma import collect_cma
from .met import collect_met

COLLECTORS = {"aic": collect_aic, "met": collect_met, "cma": collect_cma}

