import inspect
from typing import TypeVar, Type, List, Union, Any, Callable, Dict, cast

T = TypeVar('T')

__all__ = ['DiContext', 'DI']

class DiContext:
    '''Dependency injection context'''
    def __init__(self):
        self.service_types: Dict[str, Type[Any]] = {}
        self.services = {}

    def register_service(self, service_type: Type[T]) -> None:
        '''Register a service for the application'''
        key = service_type.__name__
        if key in self.service_types: raise ValueError(f"Service or type {key} is already registered")
        self.service_types[key] = service_type
        
    def register_services(self, services: List[Type[Any]]) -> None:
        '''Register a list of services for the application'''
        for service in services:
            self.register_service(service)
        
    def register_instance(self, instance) -> None:
        '''Register an instance of a service for the application'''
        self.register_service(type(instance))
        self.services[type(instance)] = instance

    def get(self, service_type: Union[Type[T], str]) -> T:
        '''Get a service by class or class name'''
        if isinstance(service_type, str): service_type = self.service_types[service_type]
        if service_type in self.services: return self.services[service_type]
        init_args_types = get_init_args(service_type)
        service = LazyInit(lambda: service_type(*[self.get(t) for t in init_args_types]))
        self.services[service_type] = service
        return cast(T, service)


def get_init_args(cls: Type[Any]) -> List[Type[Any]]:
    '''Inspect the constructor of a class'''
    sig = inspect.signature(cls.__init__)
    return [param.annotation for param in sig.parameters.values() if param.annotation is not inspect.Parameter.empty]

class LazyInit[T]:
    def __init__(self, func: Callable[[], T]):
        self._init_func = func
        self._instance = None
        
    def _initialize_inner(self) -> T: 
        if self._instance is None:
            self._instance = self._init_func()
        return self._instance
    
    def __getattribute__(self, name: str) -> Any:
        if name in {'_initialize_inner', '_init_func', '_instance'}: 
            return object.__getattribute__(self, name)
        return getattr(self._initialize_inner(), name)




DI = DiContext()