"""Bounded text-only Ollama adapter for an explicitly selected local model."""
import json
import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaBackend:
    def __init__(self, model, *, port=11434, seed=20261001, timeout=60):
        if not isinstance(model, str) or not model.strip() or len(model) > 128:
            raise ValueError("Un nom de modèle local est requis")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Port local invalide")
        if type(seed) is not int or not 0 <= seed <= 2147483647:
            raise ValueError("Seed invalide")
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 60:
            raise ValueError("Timeout invalide")
        self.model, self.port, self.seed, self.timeout = model, port, seed, timeout
        self.usage = None
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())

    def reply(self, messages):
        if not isinstance(messages, list) or not 1 <= len(messages) <= 40:
            raise ValueError("Messages invalides")
        for item in messages:
            if (not isinstance(item, dict) or set(item) != {"role", "content"}
                    or item["role"] not in {"user", "assistant", "system"}
                    or not isinstance(item["content"], str)):
                raise ValueError("Message invalide")
        payload = json.dumps({"model": self.model, "messages": messages,
                              "stream": False, "format": "json",
                              "options": {"temperature": 0, "seed": self.seed,
                                          "num_predict": 512}},
                             ensure_ascii=False).encode("utf-8")
        if len(payload) > 131072:
            raise ValueError("Contexte trop volumineux")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/chat", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = response.read(262145)
            if len(data) > 262144:
                raise ValueError("Réponse trop volumineuse")
            obj = json.loads(data)
            message = obj.get("message", {})
            text = message.get("content")
            if (obj.get("done") is not True or message.get("tool_calls")
                    or not isinstance(text, str) or not text.strip()
                    or len(text) > 16000):
                raise ValueError("Réponse texte invalide")
            self.usage = {key: obj[key] for key in
                          ("prompt_eval_count", "eval_count", "total_duration")
                          if type(obj.get(key)) is int and obj[key] >= 0}
            return text
        except Exception:
            # Neither server output nor OS errors enter the audit/error report.
            raise RuntimeError("Échec du modèle local Ollama") from None
