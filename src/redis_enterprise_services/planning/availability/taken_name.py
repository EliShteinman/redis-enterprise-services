from redis_enterprise_services.planning.availability.requested_name import RequestedName


class TakenName(RequestedName):
    cluster: str

    def describe(self) -> str:
        return f"{self.kind} {self.name} exists on {self.cluster}"
