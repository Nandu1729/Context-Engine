"""Trusted SDK composition examples. Obtain Principal through Authenticator, not user JSON."""

from ..models import Scope
from .control import opaque


def prepare_for_caller(memory, principal, tenant, session, question, budget, *, system):
    """Return context for caller-managed inference; export revocation remains caller-owned."""
    principal.authorize(tenant, session)
    return memory.assemble(Scope(principal.tenant, session), question, budget, system=system)


async def complete_with_groq(
    memory, principal, tenant, session, question, budget, *, system, client
):
    """Use an explicit provider client; never load credentials or authorize spending."""
    from ..providers.memory import MemoryProvider

    principal.authorize(tenant, session)
    return await MemoryProvider(memory, client, replay=False).complete(
        Scope(principal.tenant, session),
        question,
        budget,
        system=system,
        security_scope=opaque(
            str((principal.subject, principal.tenant, principal.role, principal.sessions))
        ),
    )
