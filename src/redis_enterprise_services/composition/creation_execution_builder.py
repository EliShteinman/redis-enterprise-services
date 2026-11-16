from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.creation_planning import CreationPlanning
from redis_enterprise_services.creation.creation_record_reader import CreationRecordReader
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor


class CreationExecutionBuilder:
    def __init__(
        self,
        *,
        saga_executor: SagaExecutor,
        public_errors: PublicErrors,
        saga_record_reader: SagaRecordReader,
        operation_store: OperationStore,
    ) -> None:
        self._saga_executor: SagaExecutor = saga_executor
        self._public_errors: PublicErrors = public_errors
        self._saga_record_reader: SagaRecordReader = saga_record_reader
        self._operation_store: OperationStore = operation_store

    def build[TPrepared](
        self, *, planning: CreationPlanning[TPrepared], record_reader: CreationRecordReader[TPrepared]
    ) -> CreationExecution[TPrepared]:
        return CreationExecution(
            planning=planning,
            saga_executor=self._saga_executor,
            outcome_translator=CreationOutcomeTranslator(
                record_reader=record_reader, public_errors=self._public_errors
            ),
            public_errors=self._public_errors,
            saga_record_reader=self._saga_record_reader,
            operation_store=self._operation_store,
        )
