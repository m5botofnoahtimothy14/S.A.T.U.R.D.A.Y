                          

import os
import sys
import logging
import threading
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import warnings

DRIVE_ROOT = "D:/AEGIS"
os.environ['AEGIS_ROOT'] = DRIVE_ROOT

TF_HOME = os.path.join(DRIVE_ROOT, ".tensorflow")
HF_HOME = os.path.join(DRIVE_ROOT, ".huggingface")
TORCH_HOME = os.path.join(DRIVE_ROOT, ".torch")
ONNX_HOME = os.path.join(DRIVE_ROOT, ".onnx")
MODEL_CACHE = os.path.join(DRIVE_ROOT, "models")

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_HUB_CACHE_DIR'] = os.path.join(TF_HOME, "hub")
os.environ['HF_HOME'] = HF_HOME
os.environ['TORCH_HOME'] = TORCH_HOME
os.environ['TRANSFORMERS_CACHE'] = os.path.join(HF_HOME, "transformers")
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

for _dir in [TF_HOME, HF_HOME, TORCH_HOME, ONNX_HOME, MODEL_CACHE]:
    os.makedirs(_dir, exist_ok=True)

logger = logging.getLogger("AEGIS.DL.Backend")

class DLBackend(Enum):
    TENSORFLOW = "tensorflow"
    PYTORCH = "pytorch"
    ONNX = "onnx"
    NUMPY = "numpy"            
    UNKNOWN = "unknown"

@dataclass
class GPUInfo:
    available: bool = False
    name: str = ""
    memory_total: int = 0
    memory_free: int = 0
    compute_capability: Tuple[int, int] = (0, 0)
    cuda_version: str = ""

@dataclass
class BackendStatus:
    tensorflow: bool = False
    tensorflow_gpu: bool = False
    pytorch: bool = False
    pytorch_gpu: bool = False
    onnx: bool = False
    onnx_gpu: bool = False
    cuda_available: bool = False
    gpu_info: GPUInfo = field(default_factory=GPUInfo)
    recommended_backend: DLBackend = DLBackend.NUMPY
    warnings: List[str] = field(default_factory=list)

class DLBackendManager:
    
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self._status: Optional[BackendStatus] = None
        self._config_dir = "data/dl_config"
        os.makedirs(self._config_dir, exist_ok=True)
        
        self._initialize_backends()
    
    def _initialize_backends(self):
        
        self._status = BackendStatus()
        self._detect_cuda()
        self._detect_tensorflow()
        self._detect_pytorch()
        self._detect_onnx()
        self._recommend_backend()
        self._log_status()
        self._save_config()
    
    def _detect_cuda(self):
        
        gpu_info = GPUInfo()
        
        try:
            import torch
            if torch.cuda.is_available():
                gpu_info.available = True
                gpu_info.name = torch.cuda.get_device_name(0)
                gpu_info.memory_total = torch.cuda.get_device_properties(0).total_memory
                gpu_info.memory_free = torch.cuda.memory_reserved(0)
                cc = torch.cuda.get_device_capability(0)
                gpu_info.compute_capability = (cc[0], cc[1])
                try:
                    gpu_info.cuda_version = torch.version.cuda
                except:
                    pass
                self._status.cuda_available = True
                logger.info(f"CUDA detected: {gpu_info.name}")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"CUDA detection failed: {e}")
        
        if not gpu_info.available:
            try:
                import subprocess
                result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], 
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    gpu_info.available = True
                    parts = result.stdout.strip().split(',')
                    gpu_info.name = parts[0].strip()
                    if len(parts) > 1:
                        gpu_info.memory_total = int(parts[1].strip().split()[0]) * 1024 * 1024
                    logger.info(f"GPU detected via nvidia-smi: {gpu_info.name}")
            except:
                pass
        
        self._status.gpu_info = gpu_info
    
    def _detect_tensorflow(self):
        
        tf_available = False
        tf_gpu = False
        
        try:
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
            os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
            
            import tensorflow as tf
            
            tf_available = True
            version = tf.__version__
            logger.info(f"TensorFlow {version} detected (cache: {TF_HOME})")
            
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
            
            gpus = tf.config.list_physical_devices('GPU')
            if gpus:
                tf_gpu = True
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"TensorFlow GPU enabled: {len(gpus)} GPU(s)")
            else:
                logger.info("TensorFlow running on CPU")
            
            tf.get_logger().setLevel('ERROR')
            warnings.filterwarnings('ignore', category=DeprecationWarning)
            warnings.filterwarnings('ignore', category=FutureWarning)
            
            self._status.tensorflow = True
            self._status.tensorflow_gpu = tf_gpu
            
        except ImportError as e:
            self._status.warnings.append(f"TensorFlow not installed: {e}")
            logger.warning("TensorFlow not available - DeepFace will use fallback")
        except Exception as e:
            self._status.warnings.append(f"TensorFlow error: {e}")
            logger.error(f"TensorFlow initialization failed: {e}")
    
    def _detect_pytorch(self):
        
        pytorch_available = False
        pytorch_gpu = False
        
        try:
            import torch
            
            pytorch_available = True
            version = torch.__version__
            logger.info(f"PyTorch {version} detected")
            
            if torch.cuda.is_available():
                pytorch_gpu = True
                logger.info(f"PyTorch CUDA enabled: {torch.version.cuda}")
            else:
                logger.info("PyTorch running on CPU")
            
            self._status.pytorch = True
            self._status.pytorch_gpu = pytorch_gpu
            
        except ImportError:
            self._status.warnings.append("PyTorch not installed")
            logger.warning("PyTorch not available")
        except Exception as e:
            self._status.warnings.append(f"PyTorch error: {e}")
            logger.error(f"PyTorch initialization failed: {e}")
    
    def _detect_onnx(self):
        
        onnx_available = False
        onnx_gpu = False
        
        try:
            import onnxruntime as ort
            
            onnx_available = True
            version = ort.__version__
            logger.info(f"ONNX Runtime {version} detected")
            
            providers = ort.get_available_providers()
            if 'CUDAExecutionProvider' in providers:
                onnx_gpu = True
                logger.info("ONNX GPU acceleration available")
            elif 'TensorrtExecutionProvider' in providers:
                onnx_gpu = True
                logger.info("ONNX TensorRT acceleration available")
            else:
                logger.info("ONNX running on CPU")
            
            self._status.onnx = True
            self._status.onnx_gpu = onnx_gpu
            
        except ImportError:
            self._status.warnings.append("ONNX Runtime not installed")
            logger.warning("ONNX Runtime not available")
        except Exception as e:
            self._status.warnings.append(f"ONNX error: {e}")
            logger.error(f"ONNX initialization failed: {e}")
    
    def _recommend_backend(self):
        
        if self._status.tensorflow and self._status.tensorflow_gpu:
            self._status.recommended_backend = DLBackend.TENSORFLOW
            logger.info("Recommended backend: TensorFlow (GPU)")
        elif self._status.pytorch and self._status.pytorch_gpu:
            self._status.recommended_backend = DLBackend.PYTORCH
            logger.info("Recommended backend: PyTorch (GPU)")
        elif self._status.tensorflow:
            self._status.recommended_backend = DLBackend.TENSORFLOW
            logger.info("Recommended backend: TensorFlow (CPU)")
        elif self._status.pytorch:
            self._status.recommended_backend = DLBackend.PYTORCH
            logger.info("Recommended backend: PyTorch (CPU)")
        elif self._status.onnx:
            self._status.recommended_backend = DLBackend.ONNX
            logger.info("Recommended backend: ONNX Runtime")
        else:
            self._status.recommended_backend = DLBackend.NUMPY
            logger.warning("No DL framework available - using NumPy fallback")
            self._status.warnings.append("No DL framework detected - using NumPy fallback")
    
    def _log_status(self):
        
        status = self._status
        logger.info("=" * 50)
        logger.info("AEGIS DL Backend Status")
        logger.info("=" * 50)
        logger.info(f"TensorFlow: {'Yes' if status.tensorflow else 'No'} {'(GPU)' if status.tensorflow_gpu else '(CPU)'}")
        logger.info(f"PyTorch: {'Yes' if status.pytorch else 'No'} {'(GPU)' if status.pytorch_gpu else '(CPU)'}")
        logger.info(f"ONNX Runtime: {'Yes' if status.onnx else 'No'} {'(GPU)' if status.onnx_gpu else '(CPU)'}")
        logger.info(f"CUDA Available: {status.cuda_available}")
        if status.gpu_info.available:
            logger.info(f"GPU: {status.gpu_info.name}")
        logger.info(f"Recommended Backend: {status.recommended_backend.value}")
        if status.warnings:
            logger.warning(f"Warnings: {status.warnings}")
        logger.info("=" * 50)
    
    def _save_config(self):
        
        config = {
            "tensorflow": {
                "available": self._status.tensorflow,
                "gpu": self._status.tensorflow_gpu
            },
            "pytorch": {
                "available": self._status.pytorch,
                "gpu": self._status.pytorch_gpu
            },
            "onnx": {
                "available": self._status.onnx,
                "gpu": self._status.onnx_gpu
            },
            "cuda": self._status.cuda_available,
            "gpu": {
                "available": self._status.gpu_info.available,
                "name": self._status.gpu_info.name,
                "memory_mb": self._status.gpu_info.memory_total // (1024 * 1024)
            },
            "recommended": self._status.recommended_backend.value
        }
        
        config_path = os.path.join(self._config_dir, "backend_config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get_status(self) -> BackendStatus:
        
        return self._status
    
    def is_available(self, backend: DLBackend) -> bool:
        
        if backend == DLBackend.TENSORFLOW:
            return self._status.tensorflow
        elif backend == DLBackend.PYTORCH:
            return self._status.pytorch
        elif backend == DLBackend.ONNX:
            return self._status.onnx
        elif backend == DLBackend.NUMPY:
            return True
        return False
    
    def get_tensorflow_session(self):
        
        if not self._status.tensorflow:
            raise RuntimeError("TensorFlow not available")
        
        import tensorflow as tf
        
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            try:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                
                config = tf.compat.v1.ConfigProto()
                config.gpu_options.allow_growth = True
                config.gpu_options.per_process_gpu_memory_fraction = 0.8
                
                return tf.compat.v1.Session(config=config)
            except Exception as e:
                logger.warning(f"TensorFlow GPU config failed: {e}")
        
        config = tf.compat.v1.ConfigProto(
            intra_op_parallelism_threads=4,
            inter_op_parallelism_threads=4
        )
        return tf.compat.v1.Session(config=config)
    
    def get_onnx_session(self, model_path: str = None):
        
        if not self._status.onnx:
            raise RuntimeError("ONNX Runtime not available")
        
        import onnxruntime as ort
        
        providers = ['CPUExecutionProvider']
        if self._status.onnx_gpu and self._status.gpu_info.available:
            if 'CUDAExecutionProvider' in ort.get_available_providers():
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            elif 'TensorrtExecutionProvider' in ort.get_available_providers():
                providers = ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
        
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 4
        sess_options.inter_op_num_threads = 4
        
        if model_path and os.path.exists(model_path):
            return ort.InferenceSession(model_path, sess_options=sess_options, providers=providers)
        
        return sess_options, providers
    
    def setup_deepface(self):
        
        logger.info("Setting up DeepFace environment on Drive D...")
        
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
        os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
        os.environ['TF_HUB_CACHE_DIR'] = os.path.join(TF_HOME, "hub")
        
        os.environ['DEEPFACE_HOME'] = os.path.join(DRIVE_ROOT, ".deepface")
        os.environ['KERAS_HOME'] = os.path.join(DRIVE_ROOT, ".keras")
        
        for _d in [os.environ['DEEPFACE_HOME'], os.environ['KERAS_HOME'], TF_HOME]:
            os.makedirs(_d, exist_ok=True)
        
        if self._status.tensorflow_gpu:
            os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
            os.environ['TF_GPU_THREAD_MODE'] = 'gpu_private'
        
        if self._status.tensorflow:
            try:
                import tensorflow as tf
                tf.get_logger().setLevel('ERROR')
                
                if self._status.tensorflow_gpu and self._status.gpu_info.available:
                    gpus = tf.config.list_physical_devices('GPU')
                    if gpus:
                        for gpu in gpus:
                            tf.config.experimental.set_memory_growth(gpu, True)
                        config = tf.compat.v1.ConfigProto()
                        config.gpu_options.allow_growth = True
                        config.gpu_options.per_process_gpu_memory_fraction = 0.8
                        tf.compat.v1.keras.backend.set_session(tf.compat.v1.Session(config=config))
                        logger.info(f"DeepFace GPU configured: {self._status.gpu_info.name}")
                else:
                    config = tf.compat.v1.ConfigProto(
                        intra_op_parallelism_threads=4,
                        inter_op_parallelism_threads=4
                    )
                    tf.compat.v1.keras.backend.set_session(tf.compat.v1.Session(config=config))
                    logger.info("DeepFace CPU configured")
                    
                return True
            except Exception as e:
                logger.error(f"DeepFace setup failed: {e}")
                return False
        
        logger.warning("DeepFace will use fallback mode (no TensorFlow)")
        return False
    
    def verify_installation(self) -> Dict[str, bool]:
        
        results = {}
        
        try:
            import tensorflow as tf
            results['tensorflow'] = True
            results['tensorflow_version'] = tf.__version__
        except:
            results['tensorflow'] = False
        
        try:
            import torch
            results['pytorch'] = True
            results['pytorch_version'] = torch.__version__
            results['cuda_available'] = torch.cuda.is_available()
        except:
            results['pytorch'] = False
        
        try:
            import onnxruntime as ort
            results['onnx'] = True
            results['onnx_version'] = ort.__version__
        except:
            results['onnx'] = False
        
        try:
            import deepface
            results['deepface'] = True
        except ImportError:
            results['deepface'] = False
        
        try:
            import faster_whisper
            results['faster_whisper'] = True
        except ImportError:
            results['faster_whisper'] = False
        
        return results

def get_backend_manager() -> DLBackendManager:
    
    return DLBackendManager()

def setup_for_deepface() -> bool:
    
    return get_backend_manager().setup_deepface()

def get_best_backend() -> DLBackend:
    
    return get_backend_manager().get_status().recommended_backend
