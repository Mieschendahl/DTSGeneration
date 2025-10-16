from pathlib import Path

### CONSTANTS ###

INSTALLATION_TIMEOUT = 600
EXECUTION_TIMEOUT = 60

### Paths ###

ASSETS_PATH = Path(__file__).parent.parent.parent / "assets"
DECLARATION_SCRIPTS_PATH = ASSETS_PATH / "declaration"
COMPARISON_SCRIPTS_PATH = ASSETS_PATH / "comparison"
EVALUATION_PATH = Path("evaluation")
PACKAGES_PATH = Path("packages")
DATA_PATH = Path("data")
LOGS_PATH = Path("logs")
EXAMPLES_PATH = Path("examples")
DECLARATIONS_PATH = Path("declarations")
COMPARISONS_PATH = Path("comparisons")
CACHE_PATH = Path("cache")
TEMPLATE_PATH = CACHE_PATH / "template"
PLAYGROUND_PATH = CACHE_PATH / "playground"
PROMPTER_PATH = CACHE_PATH / "prompter"
EXTRACTION_PATH = Path("extraction")
GENERATION_PATH = Path("generation")
COMBINED_EXTRACTION_PATH = Path(f"combined_extraction")
COMBINED_GENERATION_PATH = Path(f"combined_generation")
COMBINED_ALL_PATH = Path(f"combined_all")
BASIC_MODE_PATHS = [EXTRACTION_PATH, GENERATION_PATH]
COMBINED_MODE_PATHS = [COMBINED_EXTRACTION_PATH, COMBINED_GENERATION_PATH, COMBINED_ALL_PATH]
ALL_MODE_PATHS = BASIC_MODE_PATHS + COMBINED_MODE_PATHS
METRICS_PATH = Path("metrics")

### Exceptions ###

class ReproductionError(Exception):
    pass

class PackageDataMissingError(Exception):
    pass

class PackageInstallationError(Exception):
    pass

class CommonJSUnsupportedError(Exception):
    pass