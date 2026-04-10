
from __future__ import annotations

import json
import os
from collections import deque
from typing import Dict, List, Sequence

import numpy as np
import structlog

logger = structlog.get_logger("AEGIS.ML.Classifier")

class NeuralClassifier:
    
    def __init__(
        self,
        input_size: int = 16,
        hidden_size: int = 24,
        output_size: int = 6,
        model_path: str = "data/ml_integration/classifier.json",
    ) -> None:
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.model_path = model_path

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

        self.weights1 = np.random.randn(input_size, hidden_size) * 0.1
        self.weights2 = np.random.randn(hidden_size, output_size) * 0.1
        self.bias1 = np.zeros(hidden_size)
        self.bias2 = np.zeros(output_size)
        self.training_buffer: deque[tuple[np.ndarray, int]] = deque(maxlen=512)

        self._load()

    @staticmethod
    def _relu(values: np.ndarray) -> np.ndarray:
        return np.maximum(0.0, values)

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        shifted = values - np.max(values)
        exp_values = np.exp(shifted)
        return exp_values / (np.sum(exp_values) + 1e-12)

    def _vectorize(self, features: Sequence[float]) -> np.ndarray:
        vector = np.zeros(self.input_size, dtype=float)
        clipped = list(features)[: self.input_size]
        if clipped:
            vector[: len(clipped)] = clipped
        return vector

    def _forward(self, features: np.ndarray) -> np.ndarray:
        hidden = self._relu(np.dot(features, self.weights1) + self.bias1)
        return self._softmax(np.dot(hidden, self.weights2) + self.bias2)

    def predict(self, features: Sequence[float]) -> Dict[str, float | int | List[float]]:
        vector = self._vectorize(features)
        logits = self._forward(vector)
        best_idx = int(np.argmax(logits))
        return {
            "label": best_idx,
            "confidence": float(logits[best_idx]),
            "scores": logits.tolist(),
        }

    def learn(self, features: Sequence[float], label: int) -> None:
        if label < 0 or label >= self.output_size:
            return
        self.training_buffer.append((self._vectorize(features), label))
        if len(self.training_buffer) >= 24:
            self._train_from_buffer(epochs=8, lr=0.01)

    def _train_from_buffer(self, epochs: int, lr: float) -> None:
        if not self.training_buffer:
            return

        X = np.vstack([entry[0] for entry in self.training_buffer])
        y = np.array([entry[1] for entry in self.training_buffer], dtype=int)
        y_onehot = np.zeros((len(y), self.output_size))
        y_onehot[np.arange(len(y)), y] = 1.0

        for _ in range(epochs):
            hidden = self._relu(np.dot(X, self.weights1) + self.bias1)
            logits = np.dot(hidden, self.weights2) + self.bias2
            logits = logits - np.max(logits, axis=1, keepdims=True)
            probs = np.exp(logits)
            probs = probs / (np.sum(probs, axis=1, keepdims=True) + 1e-12)

            error = y_onehot - probs
            grad_w2 = np.dot(hidden.T, error) / len(X)
            grad_b2 = np.mean(error, axis=0)

            hidden_error = np.dot(error, self.weights2.T)
            hidden_grad = hidden_error * (hidden > 0)
            grad_w1 = np.dot(X.T, hidden_grad) / len(X)
            grad_b1 = np.mean(hidden_grad, axis=0)

            self.weights2 += lr * grad_w2
            self.bias2 += lr * grad_b2
            self.weights1 += lr * grad_w1
            self.bias1 += lr * grad_b1

        self._save()

    def _save(self) -> None:
        try:
            payload = {
                "weights1": self.weights1.tolist(),
                "weights2": self.weights2.tolist(),
                "bias1": self.bias1.tolist(),
                "bias2": self.bias2.tolist(),
            }
            with open(self.model_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
        except Exception as exc:
            logger.warning("Failed to save classifier model", error=str(exc))

    def _load(self) -> None:
        if not os.path.exists(self.model_path):
            return
        try:
            with open(self.model_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.weights1 = np.array(payload["weights1"], dtype=float)
            self.weights2 = np.array(payload["weights2"], dtype=float)
            self.bias1 = np.array(payload["bias1"], dtype=float)
            self.bias2 = np.array(payload["bias2"], dtype=float)
        except Exception as exc:
            logger.warning("Failed to load classifier model", error=str(exc))

