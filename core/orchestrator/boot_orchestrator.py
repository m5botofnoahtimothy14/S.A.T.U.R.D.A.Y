"""
AEGIS Boot Orchestrator
Manages dependency-aware module initialization
Ensures proper startup sequence and handles failures gracefully
"""

import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, Set, Any
from collections import defaultdict
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class ModulePriority(Enum):
    CRITICAL = 0      # EventBus, Config, State - must start first
    CORE = 1          # Audio, Voice, Core services
    ESSENTIAL = 2     # Identity, Security, Health
    STANDARD = 3      # UI, Services
    OPTIONAL = 4      # Vision, Social, Cloud sync
    LAZY = 5          # Heavy ML models, deep learning


@dataclass
class ModuleSpec:
    name: str
    import_path: str
    class_name: str
    priority: ModulePriority
    dependencies: List[str] = field(default_factory=list)
    lazy_init: bool = False
    init_timeout: float = 30.0
    required: bool = True
    on_init: Optional[Callable] = None
    on_shutdown: Optional[Callable] = None


@dataclass
class BootStage:
    name: str
    modules: List[str]
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: str = "pending"
    errors: List[str] = field(default_factory=list)


class BootOrchestrator:
    """
    Orchestrates module initialization in dependency-aware order.
    Supports staged boot, lazy loading, and graceful error handling.
    """
    
    def __init__(self, resource_manager=None):
        self._resource_manager = resource_manager
        self._modules: Dict[str, ModuleSpec] = {}
        self._instances: Dict[str, Any] = {}
        self._module_states: Dict[str, str] = {}
        self._boot_stages: List[BootStage] = []
        self._initialized = False
        self._boot_start_time: Optional[float] = None
        
        self._boot_order: List[str] = []
        self._stage_handlers: Dict[str, Callable] = {}
        
        self._event_bus = None
        self._config = None
    
    def register_module(self, spec: ModuleSpec):
        self._modules[spec.name] = spec
        logger.debug(f"Registered module: {spec.name} (priority={spec.priority.name})")
    
    def register_modules(self, specs: List[ModuleSpec]):
        for spec in specs:
            self.register_module(spec)
    
    def set_dependencies(self, event_bus, config):
        self._event_bus = event_bus
        self._config = config
    
    def get_module(self, name: str) -> Optional[Any]:
        return self._instances.get(name)
    
    def get_module_state(self, name: str) -> str:
        return self._module_states.get(name, "unknown")
    
    def _compute_boot_order(self) -> List[str]:
        visited: Set[str] = set()
        order: List[str] = []
        
        def visit(name: str):
            if name in visited or name not in self._modules:
                return
            visited.add(name)
            
            spec = self._modules[name]
            for dep in spec.dependencies:
                visit(dep)
            
            order.append(name)
        
        for name in self._modules:
            visit(name)
        
        self._boot_order = order
        return order
    
    def _group_by_priority(self) -> Dict[ModulePriority, List[str]]:
        by_priority = defaultdict(list)
        for name in self._boot_order:
            spec = self._modules[name]
            by_priority[spec.priority].append(name)
        return by_priority
    
    def _create_stages(self) -> List[BootStage]:
        by_priority = self._group_by_priority()
        stages = []
        
        stage_mapping = {
            ModulePriority.CRITICAL: "foundation",
            ModulePriority.CORE: "core",
            ModulePriority.ESSENTIAL: "essential",
            ModulePriority.STANDARD: "standard",
            ModulePriority.OPTIONAL: "optional",
            ModulePriority.LAZY: "lazy"
        }
        
        for priority in ModulePriority:
            if priority in by_priority:
                modules = by_priority[priority]
                stage = BootStage(
                    name=stage_mapping[priority],
                    modules=modules
                )
                stages.append(stage)
        
        self._boot_stages = stages
        return stages
    
    async def _init_module(self, name: str, timeout: float = 30.0) -> bool:
        spec = self._modules.get(name)
        if not spec:
            logger.error(f"Unknown module: {name}")
            return False
        
        self._module_states[name] = "initializing"
        
        try:
            module = await asyncio.wait_for(
                self._load_module(spec),
                timeout=timeout
            )
            
            if module is not None:
                self._instances[name] = module
                self._module_states[name] = "running"
                
                if spec.on_init and self._event_bus:
                    try:
                        spec.on_init(module, self._event_bus)
                    except Exception as e:
                        logger.warning(f"Module {name} on_init error: {e}")
                
                logger.info(f"Module initialized: {name}")
                return True
            else:
                self._module_states[name] = "failed"
                return False
                
        except asyncio.TimeoutError:
            logger.error(f"Module {name} init timeout ({timeout}s)")
            self._module_states[name] = "timeout"
            return False
        except Exception as e:
            logger.error(f"Module {name} init error: {e}")
            self._module_states[name] = "error"
            return False
    
    async def _load_module(self, spec: ModuleSpec):
        import_path = spec.import_path
        
        try:
            parts = import_path.rsplit('.', 1)
            if len(parts) == 2:
                module_name, class_name = parts
                mod = __import__(module_name, fromlist=[class_name])
                cls = getattr(mod, class_name)
            else:
                mod = __import__(import_path)
                cls = getattr(mod, spec.class_name)
            
            if spec.dependencies:
                deps = {dep: self._instances.get(dep) for dep in spec.dependencies}
                instance = cls(event_bus=self._event_bus, config=self._config, **deps)
            else:
                instance = cls(event_bus=self._event_bus, config=self._config)
            
            if hasattr(instance, 'start'):
                asyncio.create_task(instance.start())
            
            return instance
            
        except ImportError as e:
            if spec.required:
                logger.error(f"Failed to import {spec.name}: {e}")
            else:
                logger.warning(f"Optional module {spec.name} not available: {e}")
            return None
        except Exception as e:
            if spec.required:
                logger.error(f"Failed to load {spec.name}: {e}")
            else:
                logger.warning(f"Optional module {spec.name} failed: {e}")
            return None
    
    async def boot(self) -> Dict[str, bool]:
        """
        Execute the boot sequence.
        Returns dict of module name -> success status.
        """
        if self._initialized:
            logger.warning("BootOrchestrator already initialized")
            return {name: state == "running" for name, state in self._module_states.items()}
        
        self._boot_start_time = time.time()
        self._compute_boot_order()
        stages = self._create_stages()
        
        results = {}
        
        logger.info("=" * 60)
        logger.info("AEGIS BOOT SEQUENCE STARTING")
        logger.info("=" * 60)
        
        for stage in stages:
            stage.started_at = time.time()
            stage.status = "running"
            
            logger.info(f"\n[STAGE: {stage.name.upper()}]")
            logger.info(f"  Modules: {', '.join(stage.modules)}")
            
            stage_results = await self._boot_stage(stage)
            results.update(stage_results)
            
            stage.completed_at = time.time()
            stage.status = "completed" if not stage.errors else "completed_with_errors"
            
            elapsed = stage.completed_at - stage.started_at
            logger.info(f"  Stage completed in {elapsed:.2f}s")
            
            if stage.errors:
                logger.warning(f"  Errors: {len(stage.errors)}")
        
        total_time = time.time() - self._boot_start_time
        logger.info("\n" + "=" * 60)
        logger.info(f"AEGIS BOOT COMPLETE ({total_time:.2f}s)")
        logger.info("=" * 60)
        
        successful = sum(1 for v in results.values() if v)
        total = len(results)
        logger.info(f"Modules: {successful}/{total} successful")
        
        self._initialized = True
        return results
    
    async def _boot_stage(self, stage: BootStage) -> Dict[str, bool]:
        results = {}
        
        if stage.name == "foundation":
            for module_name in stage.modules:
                success = await self._init_module(module_name, timeout=60.0)
                results[module_name] = success
                if not success and self._modules[module_name].required:
                    stage.errors.append(f"{module_name}: required module failed")
        else:
            tasks = []
            for module_name in stage.modules:
                spec = self._modules[module_name]
                tasks.append(self._init_module(module_name, timeout=spec.init_timeout))
            
            stage_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for module_name, result in zip(stage.modules, stage_results):
                if isinstance(result, Exception):
                    logger.error(f"Stage module {module_name} exception: {result}")
                    results[module_name] = False
                    if self._modules[module_name].required:
                        stage.errors.append(f"{module_name}: {str(result)}")
                else:
                    results[module_name] = result
        
        return results
    
    async def shutdown(self):
        """Shutdown all modules in reverse order."""
        logger.info("AEGIS SHUTDOWN INITIATED")
        
        for name in reversed(self._boot_order):
            spec = self._modules.get(name)
            instance = self._instances.get(name)
            
            if instance and spec and spec.on_shutdown:
                try:
                    spec.on_shutdown(instance)
                    logger.info(f"Module shutdown: {name}")
                except Exception as e:
                    logger.error(f"Module {name} shutdown error: {e}")
            
            self._module_states[name] = "stopped"
        
        self._instances.clear()
        self._initialized = False
        logger.info("AEGIS SHUTDOWN COMPLETE")
    
    def get_boot_stats(self) -> Dict[str, Any]:
        if not self._boot_start_time:
            return {"status": "not_started"}
        
        total_time = time.time() - self._boot_start_time if self._initialized else None
        
        return {
            "initialized": self._initialized,
            "total_time": total_time,
            "modules_loaded": len(self._instances),
            "modules_failed": sum(1 for s in self._module_states.values() if s == "error"),
            "stages": [
                {
                    "name": s.name,
                    "status": s.status,
                    "module_count": len(s.modules),
                    "errors": len(s.errors),
                    "elapsed": (s.completed_at - s.started_at) if s.completed_at else None
                }
                for s in self._boot_stages
            ]
        }
