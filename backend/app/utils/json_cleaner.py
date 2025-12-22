"""
Utilitaire de nettoyage JSON pour les réponses LLM
Gère les backticks markdown, les caractères de contrôle, et les strings multi-lignes
"""
import re
import json
import logging
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)

def clean_llm_json_response(raw_response: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Nettoie une réponse LLM contenant du JSON.
    
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
        # Prendre le plus gros bloc JSON trouvé
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
    
    # Étape 3: Trouver la fin du JSON (dernier } ou ] correspondant)
    # On cherche de la fin vers le début
    last_brace = text.rfind('}')
    last_bracket = text.rfind(']')
    
    if last_brace == -1 and last_bracket == -1:
        return None, "No closing bracket found"
    
    end_pos = max(last_brace, last_bracket) + 1
    text = text[:end_pos]
    
    # Étape 4: Échapper les newlines dans les strings JSON
    def escape_newlines_in_strings(s: str) -> str:
        """Échappe les \n et \t réels dans les strings JSON"""
        result = []
        in_string = False
        i = 0
        while i < len(s):
            char = s[i]
            
            # Gestion des échappements existants
            if char == '\\' and i + 1 < len(s):
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
                    result.append(' ')  # Remplacer autres caractères de contrôle
                else:
                    result.append(char)
            else:
                # Hors string, garder les whitespaces normaux
                result.append(char)
            
            i += 1
        
        return ''.join(result)
    
    text = escape_newlines_in_strings(text)
    
    # Étape 5: Essayer de parser
    try:
        parsed = json.loads(text)
        return parsed, None
    except json.JSONDecodeError as e:
        # Tentative de réparation: supprimer les trailing commas
        text_fixed = re.sub(r',(\s*[}\]])', r'\1', text)
        try:
            parsed = json.loads(text_fixed)
            logger.info("JSON parsed after removing trailing commas")
            return parsed, None
        except json.JSONDecodeError:
            pass
        
        return None, f"JSON parse error at position {e.pos}: {e.msg}"


def safe_parse_agent_response(raw_response: str, agent_id: str = "unknown", mode: str = "unknown") -> dict:
    """
    Parse la réponse d'un agent de manière sécurisée.
    Retourne toujours un dict utilisable.
    
    Args:
        raw_response: La réponse brute du LLM
        agent_id: ID de l'agent (pour logging)
        mode: Mode de l'agent (pour logging)
    
    Returns:
        dict avec soit le contenu parsé, soit le raw préservé avec l'erreur
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
