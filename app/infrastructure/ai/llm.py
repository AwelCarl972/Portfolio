"""Adaptateurs LLM. L'IA ne voit QUE du texte déjà anonymisé."""
import os
import re

SYSTEM_PROMPT = (
    "Tu es un expert en maintenance de parc (véhicules, engins) à La Réunion, où les pièces arrivent "
    "par fret maritime (30-45 j) ou aérien (4-7 j). Les identifiants du type ACTIF_xxxx, LIEU_xxxx, "
    "CLIENT_xxxx, TEL_xxxx, REF_xxxx sont des alias opaques : reprends-les tels quels, ne tente pas de "
    "les deviner. Réponds en français, en 4 sections courtes : SYNTHÈSE, CAUSE PROBABLE, "
    "ACTIONS (priorisées), APPROVISIONNEMENT (mer vs air)."
)

_ALIAS = re.compile(r"\b(?:ACTIF|LIEU|CLIENT)_[0-9A-F]{4,16}\b")


class AnthropicLLM:
    def __init__(self, model: str | None = None):
        import anthropic  # import paresseux : dépendance optionnelle
        self._client = anthropic.Anthropic()
        self._model = model or os.getenv("LLM_MODEL", "claude-sonnet-5-5")

    def complete(self, system: str, user: str) -> str:
        r = self._client.messages.create(model=self._model, max_tokens=700, system=system,
                                         messages=[{"role": "user", "content": user}])
        return r.content[0].text


class OfflineLLM:
    """Simulateur déterministe : démo sans clé API ni réseau. Réutilise les alias reçus."""

    def complete(self, system: str, user: str) -> str:
        found = list(dict.fromkeys(_ALIAS.findall(user)))
        actif = next((a for a in found if a.startswith("ACTIF")), "l'actif")
        lieu = next((a for a in found if a.startswith("LIEU")), "le site")
        urgent = "COMMANDER_AIR" in user or "RUPTURE" in user
        appro = ("Délai maritime incompatible avec l'échéance : commander en AÉRIEN dès aujourd'hui."
                 if urgent else "Commande par fret maritime suffisante si passée avant la date limite indiquée.")
        return (f"SYNTHÈSE : {actif} présente une défaillance récurrente avec des intervalles de panne qui "
                f"raccourcissent ; immobilisation constatée sur {lieu}.\n"
                f"CAUSE PROBABLE : usure prématurée du composant signalé (injection / circuit concerné) ; "
                f"à confirmer au banc avant remplacement.\n"
                f"ACTIONS : 1) Planifier {actif} en atelier cette semaine. 2) Contrôler les composants "
                f"voisins (filtration, alimentation). 3) Prévoir un véhicule de remplacement sur {lieu}.\n"
                f"APPROVISIONNEMENT : {appro}\n"
                f"[Réponse simulée hors-ligne — définir ANTHROPIC_API_KEY pour un vrai LLM]")


def build_llm():
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicLLM()
    return OfflineLLM()
