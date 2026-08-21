"""
Salesforce Configuration for Digital Humans Agents

gem:CONF-01 (LOT-E bis) — this module used to carry a real, committed org
identity as dataclass defaults: a working org alias, the owner's Salesforce
username, the 18-char org id and the org's instance URL. Those four values are
deliberately not reproduced here; they are in the git history and the org they
designate should be treated as exposed.

`from_project()` fell back to those values field by field whenever a project
did not carry its own. A project whose credentials failed to load therefore
kept working — against the wrong org. That is a cross-tenant read on one side
and a deployment landing in someone else's org on the other, both silent.

There is no identity default any more. Values come from the single .env via
`app.config.settings` (SF_ORG_ALIAS, SF_USERNAME, SF_ORG_ID, SF_INSTANCE_URL)
and are `None` when unset. Construction never raises — the module-level
singleton is imported at boot by agent_executor, pm_orchestrator_service_v2 and
agent_tester, so a raising constructor would stop the backend from starting.
The failure is raised at USE time instead, by `require()`.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Fields that identify WHICH Salesforce org is being talked to. Getting one of
# these wrong is a cross-tenant incident, not a misconfiguration.
IDENTITY_FIELDS = ("org_alias", "username", "org_id", "instance_url")


class SalesforceConfigError(RuntimeError):
    """Raised when an operation needs org identity that is not configured."""


@dataclass
class SalesforceConfig:
    """Salesforce connection configuration.

    Identity fields default to None. Use `require()` before any operation that
    reaches an org.
    """

    # Org identity — no default. See module docstring.
    org_alias: Optional[str] = field(default_factory=lambda: settings.SF_ORG_ALIAS or None)
    username: Optional[str] = field(default_factory=lambda: settings.SF_USERNAME or None)
    org_id: Optional[str] = field(default_factory=lambda: settings.SF_ORG_ID or None)
    instance_url: Optional[str] = field(default_factory=lambda: settings.SF_INSTANCE_URL or None)

    # Not an identity: the API version is the same for every org.
    api_version: str = field(default_factory=lambda: settings.SF_API_VERSION)

    # Paths (centralized via config.py settings)
    sfdx_project_path: str = field(default_factory=lambda: str(settings.SFDX_PROJECT_PATH))
    force_app_path: str = field(default_factory=lambda: str(settings.FORCE_APP_PATH))

    def missing_identity(self) -> list:
        """Return the identity fields that are not set."""
        return [name for name in IDENTITY_FIELDS if not getattr(self, name, None)]

    def is_configured(self) -> bool:
        """True when every identity field is set."""
        return not self.missing_identity()

    def require(self, *fields_required: str) -> "SalesforceConfig":
        """
        Assert that the named fields are set, and return self for chaining.

        Called with no argument, requires the full org identity. Raise rather
        than let a command run against whatever org happens to be configured.
        """
        names = fields_required or IDENTITY_FIELDS
        missing = [name for name in names if not getattr(self, name, None)]
        if missing:
            raise SalesforceConfigError(
                "Salesforce org identity is not configured: "
                + ", ".join(missing)
                + ". Set SF_ORG_ALIAS / SF_USERNAME / SF_ORG_ID / SF_INSTANCE_URL "
                "in backend/.env for the default org, or connect the project so "
                "its own credentials are used (SalesforceConfig.from_project). "
                "Refusing to fall back to another org."
            )
        return self

    @classmethod
    def from_project(cls, project) -> "SalesforceConfig":
        """
        ARCH-002 / gem:CONF-01: build a config from a Project, with NO fallback.

        The previous implementation filled each missing field from the class
        defaults, so a half-configured project silently borrowed the default
        org's identity. A project that cannot supply its own org is an error.
        """
        instance_url = getattr(project, "sf_instance_url", None)
        username = getattr(project, "sf_username", None)
        org_id = getattr(project, "sf_org_id", None)

        if not instance_url:
            raise SalesforceConfigError(
                f"Project {getattr(project, 'id', '?')} has no sf_instance_url; "
                "refusing to fall back to the default org."
            )

        config = cls(
            org_alias=org_id or None,
            username=username or None,
            org_id=org_id or None,
            instance_url=instance_url,
        )
        missing = config.missing_identity()
        if missing:
            logger.warning(
                "[SalesforceConfig] Project %s is partially configured, missing: %s. "
                "These stay unset — no value is borrowed from the default org.",
                getattr(project, "id", "?"),
                ", ".join(missing),
            )
        return config


# Singleton instance (default org, used when no project context is available).
# Constructing it never raises: it is imported at module load by several
# services. When nothing is configured its identity fields are None and any
# real use goes through require(), which fails loudly.
salesforce_config = SalesforceConfig()

if not salesforce_config.is_configured():
    logger.warning(
        "[SalesforceConfig] No default Salesforce org configured (missing: %s). "
        "Operations that need one will fail explicitly rather than fall back to "
        "another org. Set SF_ORG_ALIAS / SF_USERNAME / SF_ORG_ID / "
        "SF_INSTANCE_URL in backend/.env if a default org is wanted.",
        ", ".join(salesforce_config.missing_identity()),
    )

# Agent-specific paths
AGENT_PATHS: Dict[str, Dict[str, str]] = {
    "diego": {  # Apex Developer
        "classes": "classes",
        "triggers": "triggers",
    },
    "zara": {  # LWC Developer
        "lwc": "lwc",
        "aura": "aura",
    },
    "raj": {  # Admin/Config
        "objects": "objects",
        "flows": "flows",
        "permissionsets": "permissionsets",
        "profiles": "profiles",
    },
    "elena": {  # QA
        "classes": "classes",  # For test classes
    }
}


def get_agent_path(agent_name: str, component_type: str) -> str:
    """Get the file path for an agent's component type"""
    agent_name = agent_name.lower()
    if agent_name not in AGENT_PATHS:
        raise ValueError(f"Unknown agent: {agent_name}")

    if component_type not in AGENT_PATHS[agent_name]:
        raise ValueError(f"Agent {agent_name} doesn't handle {component_type}")

    subpath = AGENT_PATHS[agent_name][component_type]
    return f"{salesforce_config.force_app_path}/{subpath}"


def get_sfdx_command(command: str) -> str:
    """
    Build a SFDX command with the default org.

    gem:CONF-01: refuses to build a command when no default org is configured,
    rather than emitting `--target-org None` or, as before, silently targeting
    the hardcoded development org.
    """
    salesforce_config.require("org_alias")
    return f"sf {command} --target-org {salesforce_config.org_alias}"
