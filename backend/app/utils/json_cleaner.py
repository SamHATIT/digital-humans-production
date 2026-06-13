"""
Utilitaire de nettoyage JSON pour les réponses LLM
Gère les backticks markdown, les caractères de contrôle, les strings multi-lignes,
et les JSON tronqués (réparation automatique)

Updated: 2025-12-22
"""
import re
import json
import logging
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)


def repair_truncated_json(text: str) -> str:
    """
    Répare un JSON tronqué en fermant les structures ouvertes.
    Trouve le dernier point valide et ferme proprement.
    """
    # Parcourir pour trouver les structures ouvertes
    in_string = False
    escape_next = False
    stack = []  # Stack de '{' et '['
    
    i = 0
    while i < len(text):
        char = text[i]
        
        if escape_next:
            escape_next = False
            i += 1
            continue
            
        if char == '\\' and in_string:
            escape_next = True
            i += 1
            continue
            
        if char == '"':
            in_string = not in_string
            i += 1
            continue
            
        if in_string:
            i += 1
            continue
        
        if char == '{':
            stack.append('{')
        elif char == '[':
            stack.append('[')
        elif char == '}':
            if stack and stack[-1] == '{':
                stack.pop()
                i + 1
        elif char == ']':
            if stack and stack[-1] == '[':
                stack.pop()
                i + 1
        elif char == ',' and not stack:
            # Virgule au niveau racine après une valeur complète
            pass
        
        i += 1
    
    # Si on est dans une string non fermée ou avec des structures ouvertes
    if in_string or stack:
        # Trouver un bon point de coupure
        # Chercher la dernière virgule ou fin de valeur avant la troncature
        text[:len(text)]
        
        # Patterns de fin de valeur valide
        # On cherche de la fin vers le début
        cut_pos = len(text)
        
        # Chercher la dernière structure complète
        # Méthode: remonter jusqu'à trouver un point stable
        for pos in range(len(text) - 1, max(0, len(text) - 500), -1):
            char = text[pos]
            if char in '}]':
                # Vérifier si c'est une fermeture valide
                test_text = text[:pos + 1]
                # Compter les structures
                opens = test_text.count('{') + test_text.count('[')
                closes = test_text.count('}') + test_text.count(']')
                if opens >= closes:
                    cut_pos = pos + 1
                    break
            elif char == ',' and pos > 10:
                # Une virgule pourrait être un bon point de coupure
                cut_pos = pos
                break
        
        text = text[:cut_pos].rstrip().rstrip(',')
    
    # Recompter et fermer les structures
    final_stack = []
    in_string = False
    escape_next = False
    
    for char in text:
        if escape_next:
            escape_next = False
            continue
        if char == '\\' and in_string:
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == '{':
            final_stack.append('}')
        elif char == '[':
            final_stack.append(']')
        elif char == '}' and final_stack and final_stack[-1] == '}':
            final_stack.pop()
        elif char == ']' and final_stack and final_stack[-1] == ']':
            final_stack.pop()
    
    # Fermer les structures ouvertes
    while final_stack:
        text += final_stack.pop()
    
    return text


def escape_control_chars_in_strings(s: str) -> str:
    """Échappe les caractères de contrôle dans les strings JSON"""
    result = []
    in_string = False
    i = 0
    
    while i < len(s):
        char = s[i]
        
        # Gestion des échappements existants
        if char == '\\' and i + 1 < len(s) and in_string:
            result.append(char)
            result.append(s[i + 1])
            i += 2
            continue
        
        # Toggle string mode
        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue
        
        # Dans une string, échapper les caractères de contrôle
        if in_string:
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            elif ord(char) < 32:
                result.append(' ')
            else:
                result.append(char)
        else:
            result.append(char)
        
        i += 1
    
    return ''.join(result)



_VALID_JSON_ESCAPES = set('"\\/bfnrtu')
_DANGLING_KEY_RE = re.compile(r',?\s*"(?:[^"\\]|\\.)*"\s*:?\s*$')


def _sanitize_invalid_escapes(s: str) -> str:
    """Supprime le backslash des sequences d'echappement invalides dans les strings."""
    out = []
    i, n, in_str = 0, len(s), False
    while i < n:
        c = s[i]
        if in_str:
            if c == '\\':
                if i + 1 < n and s[i + 1] in _VALID_JSON_ESCAPES:
                    out.append(c); out.append(s[i + 1]); i += 2; continue
                i += 1; continue
            if c == '"':
                in_str = False
            out.append(c); i += 1
        else:
            if c == '"':
                in_str = True
            out.append(c); i += 1
    return ''.join(out)


def _close_truncated_json_lifo(s):
    """Ferme un JSON tronque meme coupe EN PLEIN MILIEU d'une string.

    Scan string-aware : enregistre les points surs (token termine, hors string)
    avec un snapshot de la pile d'ouvertures, puis recule depuis la fin pour
    trouver le dernier point fermable en LIFO. Gere le cas que repair_truncated_json
    ne gere pas (Unterminated string). Retourne (data|None, pos_de_coupe).
    """
    stack = []
    in_str = esc = False
    safe = []
    for i, c in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
                safe.append((i + 1, tuple(stack)))
            continue
        if c == '"':
            in_str = True
        elif c in '{[':
            stack.append(c); safe.append((i + 1, tuple(stack)))
        elif c in '}]':
            if stack:
                stack.pop()
            safe.append((i + 1, tuple(stack)))
        elif c == ',':
            safe.append((i, tuple(stack)))
    if not in_str:
        safe.append((len(s), tuple(stack)))
    closer = {'{': '}', '[': ']'}
    for tried, (pos, st) in enumerate(reversed(safe)):
        if tried > 400:
            break
        base = s[:pos].rstrip().rstrip(',')
        for cand in (base, _DANGLING_KEY_RE.sub('', base)):
            full = cand + ''.join(closer[o] for o in reversed(st))
            try:
                return json.loads(full, strict=False), pos
            except Exception:
                pass
    return None, 0


def clean_llm_json_response(raw_response: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Nettoie une réponse LLM contenant du JSON.
    
    Handles:
    - Markdown code blocks (```json ... ```)
    - Text before/after JSON
    - Control characters in strings  
    - Trailing commas
    - Truncated JSON (auto-repair)
    
    Returns:
        Tuple[parsed_json, error_message]
        - Si succès: (dict/list, None)
        - Si échec: (None, error_message)
    """
    if not raw_response:
        return None, "Empty response"
    
    text = raw_response.strip()
    
    # Étape 1: Retirer les backticks markdown
    json_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    matches = re.findall(json_block_pattern, text)
    if matches:
        text = max(matches, key=len).strip()
    
    # Étape 2: Trouver le début du JSON
    first_brace = text.find('{')
    first_bracket = text.find('[')
    
    if first_brace == -1 and first_bracket == -1:
        return None, "No JSON object or array found"
    
    start_pos = first_brace if first_bracket == -1 else (
        first_bracket if first_brace == -1 else min(first_brace, first_bracket)
    )
    
    if start_pos > 0:
        text = text[start_pos:]
    
    # Étape 3: Échapper les caractères de contrôle
    text = escape_control_chars_in_strings(text)
    
    # Étape 4: Tenter le parsing direct
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass
    
    # Étape 5: Retirer trailing commas
    text_clean = re.sub(r',(\s*[}\]])', r'\1', text)
    try:
        return json.loads(text_clean), None
    except json.JSONDecodeError:
        pass
    
    # Étape 6: Réparer JSON tronqué
    text_repaired = repair_truncated_json(text)
    try:
        parsed = json.loads(text_repaired)
        logger.info(f"JSON repaired: {len(text)} -> {len(text_repaired)} chars")
        return parsed, None
    except json.JSONDecodeError:
        pass
    
    # Étape 7: Trailing commas sur version réparée
    text_repaired = re.sub(r',(\s*[}\]])', r'\1', text_repaired)
    try:
        parsed = json.loads(text_repaired)
        logger.info("JSON parsed after repair + trailing comma fix")
        return parsed, None
    except json.JSONDecodeError:
        pass

    # Etape 8: fermeture LIFO string-aware (gere la coupe en plein milieu d'une
    # string, cas non couvert par repair_truncated_json). Filet ultime.
    sanitized = _sanitize_invalid_escapes(text)
    data, pos = _close_truncated_json_lifo(sanitized)
    if data is not None:
        pct = 100.0 * pos / max(len(sanitized), 1)
        logger.warning(f"JSON recovered via LIFO close at {pos}/{len(sanitized)} ({pct:.1f}%)")
        return data, None
    return None, "JSON parse error: unrecoverable even after LIFO close"


def safe_parse_agent_response(raw_response: str, agent_id: str = "unknown", mode: str = "unknown") -> dict:
    """
    Parse la réponse d'un agent de manière sécurisée.
    Retourne toujours un dict utilisable.
    """
    parsed, error = clean_llm_json_response(raw_response)
    
    if parsed is not None:
        logger.debug(f"[{agent_id}/{mode}] JSON parsed successfully")
        return parsed
    else:
        logger.warning(f"[{agent_id}/{mode}] JSON parse failed: {error}")
        return {
            "raw": raw_response,
            "parse_error": error
        }


# Test
if __name__ == "__main__":
    test_cases = [
        ('Basic', '```json\n{"key": "value"}\n```'),
        ('With text', 'Here is the JSON:\n```json\n{"key": "value"}\n```\nDone!'),
        ('Raw JSON', '{"key": "value"}'),
        ('Multiline string', '{"key": "value with\nnewline"}'),
        ('Trailing comma', '{"items": [1, 2, 3,]}'),
        ('Nested', '{"a": {"b": "c"}, "d": [1, 2]}'),
        ('Truncated object', '{"a": 1, "b": {"c": 2, "d": [1, 2, 3'),
        ('Truncated array', '{"items": [{"id": 1}, {"id": 2}, {"id":'),
        ('Truncated string', '{"name": "hello wor'),
        ('Truncated mid-value', '{"count": 123, "items": [{"x": 1}, {"x": 2'),
    ]
    
    print("=== JSON Cleaner Tests ===\n")
    for name, test in test_cases:
        result, error = clean_llm_json_response(test)
        status = "✅" if result else "❌"
        print(f"{status} {name}")
        if result:
            print(f"   Parsed: {result}")
        else:
            print(f"   Error: {error}")
        print()
