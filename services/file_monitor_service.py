class FileMonitorService:
    def __init__(self):
        self.monitored_projects = set()
        self.stop_event = None

    def start_monitoring(self, project_key, project_path, callback):
        pass

    def stop_all_monitoring(self):
        pass


file_monitor = FileMonitorService()
