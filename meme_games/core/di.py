import inspect
from typing import TypeVar, Type, List, Union, Any, Dict, cast

T = TypeVar('T')

__all__ = ['DiContext', 'DI']

class DiContext:
    '''Dependency injection context. Services are singletons, built on first request.'''
    def __init__(self):
        self.service_types: Dict[str, Type[Any]] = {}
        self.services = {}

    def register_service(self, service_type: Type[T]) -> None:
        '''Register a service for the application. Re-registering the same type is a no-op.'''
        key = service_type.__name__
        registered = self.service_types.get(key)
        if registered and registered is not service_type:
            raise ValueError(f"A different service is already registered as {key}")
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
        '''Get a service by class or class name, building its dependencies first'''
        if isinstance(service_type, str): service_type = self.service_types[service_type]
        if service_type not in self.services:
            deps = get_init_args(service_type)
            for d in deps:
                if not isinstance(d, type): raise TypeError(
                    f"Cannot build {service_type.__name__}: dependency {d!r} is not a class. "
                    "Services take concrete classes, and instances like the database must be registered first.")
            self.register_service(service_type)
            self.services[service_type] = service_type(*[self.get(t) for t in deps])
        return cast(T, self.services[service_type])

    def reset(self) -> None:
        '''Drop every built instance. For tests that need a fresh database.'''
        self.services.clear()


def get_init_args(cls: Type[Any]) -> List[Type[Any]]:
    '''Inspect the constructor of a class'''
    sig = inspect.signature(cls.__init__)
    return [param.annotation for param in sig.parameters.values() if param.annotation is not inspect.Parameter.empty]


DI = DiContext()
