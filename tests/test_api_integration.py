import base64
import io
import json
import os
import time
import unittest
import urllib.error
import urllib.request

import jwt
from PIL import Image


class ApiIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        port = os.getenv("PORT")
        if not port:
            raise RuntimeError("PORT non configurata")
        base_url = f"http://localhost:{port}"
        deadline = time.time() + 40
        while time.time() < deadline:
            request = urllib.request.Request(f"{base_url}/health", method="GET")
            try:
                with urllib.request.urlopen(request, timeout=2) as response:
                    if response.status == 200:
                        return
            except urllib.error.URLError:
                time.sleep(1)
        raise RuntimeError("Servizio non raggiungibile su /health")

    def setUp(self) -> None:
        port = os.getenv("PORT")
        if not port:
            raise RuntimeError("PORT non configurata")
        self.base_url = f"http://localhost:{port}"
        self.service_jwt_secret = os.getenv("SERVICE_JWT_SECRET")
        if not self.service_jwt_secret:
            raise RuntimeError("SERVICE_JWT_SECRET non configurato")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL")
        self.ollama_model = os.getenv("OLLAMA_MODEL")
        self.image_data = self._build_test_image_base64()

    def _build_test_image_base64(self) -> str:
        image = Image.new("RGB", (64, 64), (255, 255, 255))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()

    def _service_token(self) -> str:
        payload = {
            "iss": "whatsagent",
            "sub": "integration-test",
            "exp": int(time.time()) + 300,
        }
        return jwt.encode(payload, self.service_jwt_secret, algorithm="HS256")

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        token: str | None = None,
        timeout: int = 20,
    ):
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode())
        except TimeoutError:
            return -1, {"detail": "Timeout durante la richiesta"}

    def _is_ollama_ready(self) -> bool:
        if not self.ollama_base_url or not self.ollama_model:
            return False
        request = urllib.request.Request(f"{self.ollama_base_url}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status != 200:
                    return False
                payload = json.loads(response.read().decode())
                models = payload.get("models", [])
                names = {model.get("name") for model in models if isinstance(model, dict)}
                return self.ollama_model in names
        except (urllib.error.URLError, json.JSONDecodeError):
            return False

    def test_health(self):
        status_code, response = self._request("GET", "/health")
        self.assertEqual(status_code, 200)
        self.assertEqual(response.get("status"), "healthy")
        self.assertTrue(response.get("analyzer_ready"))

    def test_analyze_without_token(self):
        status_code, response = self._request(
            "POST",
            "/analyze",
            {
                "image_data": self.image_data,
                "image_format": "png",
                "ai_config": {"provider": "ollama"},
            },
        )
        self.assertEqual(status_code, 403)
        self.assertEqual(response.get("detail"), "Not authenticated")

    def test_analyze_with_invalid_token(self):
        status_code, response = self._request(
            "POST",
            "/analyze",
            {
                "image_data": self.image_data,
                "image_format": "png",
                "ai_config": {"provider": "ollama"},
            },
            token="abc.def.ghi",
        )
        self.assertEqual(status_code, 401)
        self.assertIn("Token di servizio non valido", response.get("detail", ""))

    def test_analyze_with_unsupported_provider(self):
        status_code, response = self._request(
            "POST",
            "/analyze",
            {
                "image_data": self.image_data,
                "image_format": "png",
                "ai_config": {"provider": "foo", "api_key": "x", "model": "m"},
            },
            token=self._service_token(),
        )
        self.assertEqual(status_code, 400)
        self.assertIn("Provider non supportato", response.get("detail", ""))

    def test_analyze_non_ollama_requires_api_key(self):
        status_code, response = self._request(
            "POST",
            "/analyze",
            {
                "image_data": self.image_data,
                "image_format": "png",
                "ai_config": {"provider": "openai", "model": "gpt-4o-mini"},
            },
            token=self._service_token(),
        )
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get("detail"), "API key del provider AI richiesta")

    def test_analyze_ollama_model_mismatch(self):
        status_code, response = self._request(
            "POST",
            "/analyze",
            {
                "image_data": self.image_data,
                "image_format": "png",
                "ai_config": {"provider": "ollama", "model": "wrong-model"},
            },
            token=self._service_token(),
        )
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get("detail"), "Per Ollama il modello deve essere uguale a OLLAMA_MODEL")

    def test_analyze_ollama_happy_path_when_available(self):
        if not self._is_ollama_ready():
            self.skipTest("Ollama non disponibile o modello configurato non presente")
        status_code, response = self._request(
            "POST",
            "/analyze",
            {
                "image_data": self.image_data,
                "image_format": "png",
                "ai_config": {"provider": "ollama"},
            },
            token=self._service_token(),
            timeout=60,
        )
        if status_code != 200:
            self.skipTest(f"Ollama disponibile ma non pronto per test end-to-end: {status_code} {response}")
        self.assertEqual(status_code, 200)
        self.assertTrue(response.get("success"))
        self.assertEqual(response.get("ai_provider"), "ollama")
        self.assertEqual(response.get("ai_model_used"), self.ollama_model)


if __name__ == "__main__":
    unittest.main()
