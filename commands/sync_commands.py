"""
Sync-specific command implementations
Handles file synchronization operations across project versions
"""

from typing import Dict, Any

from utils.async_base import AsyncCommand, AsyncResult, ProcessError
from services.project_group_service import ProjectGroup


class SyncRunTestsCommand(AsyncCommand):
    """Standardized command for syncing run_tests.sh from pre-edit"""

    def __init__(self, project_group: ProjectGroup, sync_service, **kwargs):
        super().__init__(**kwargs)
        self.project_group = project_group
        self.sync_service = sync_service

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the sync run tests command"""
        try:
            self._update_progress("Syncing run_tests.sh from pre-edit...", "info")

            # Sync run_tests.sh from pre-edit to other versions
            sync_result = await self.sync_service.sync_file_from_pre_edit(
                self.project_group, "run_tests.sh"
            )

            if sync_result.is_error:
                return AsyncResult.error_result(sync_result.error)

            result_data = {
                "message": f"Sync completed for {self.project_group.name}",
                "file_name": "run_tests.sh",
                "synced_paths": (
                    sync_result.data.synced_paths if sync_result.data else []
                ),
                "failed_syncs": (
                    sync_result.data.failed_syncs if sync_result.data else []
                ),
                "success_count": (
                    sync_result.data.success_count if sync_result.data else 0
                ),
                "total_targets": (
                    sync_result.data.total_targets if sync_result.data else 0
                ),
            }

            if sync_result.is_partial:
                self._update_progress("Sync partially completed", "warning")
                return AsyncResult.partial_result(result_data, sync_result.error)
            else:
                self._update_progress("Sync completed successfully", "success")
                return AsyncResult.success_result(result_data)

        except Exception as e:
            self.logger.exception(f"Sync command failed for {self.project_group.name}")
            return AsyncResult.error_result(
                ProcessError(f"Sync failed: {str(e)}", error_code="SYNC_ERROR")
            )
