import inspect

class DiContext:
    '''Dependency injection context'''
    def __init__(self):
        self.service_types = {}
        self.services = {}

    def register_service(self, service_type: type):
        '''Register a service for the application'''
        key = service_type.__name__
        if key in self.service_types: raise ValueError(f"Service or type {key} is already registered")
        self.service_types[key] = service_type
        
    def register_services(self, services: list[type]):
        '''Register a list of services for the application'''
        for service in services:
            self.register_service(service)
        
    def register_instance(self, instance):
        '''Register an instance of a service for the application'''
        self.register_service(type(instance))
        self.services[type(instance)] = instance

    def get(self, service_type: type|str):
        '''Get a service by class or class name'''
        if isinstance(service_type, str): service_type = self.service_types[service_type]
        if service_type in self.services: return self.services[service_type]
        init_args_types = get_init_args(service_type)
        service = service_type(*[self.get(t) for t in init_args_types])
        self.services[service_type] = service
        return service


def get_init_args(cls):
    '''Inspect the constructor of a class'''
    sig = inspect.signature(cls.__init__)
    return [param.annotation for param in sig.parameters.values() if param.annotation is not inspect.Parameter.empty]