"""Explicit, test-only bootstrap credentials; production has no usable default."""
import os

os.environ["INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD"] = "TestBootstrapPassword42!"
