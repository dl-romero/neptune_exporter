class Gauge:
    def __init__(self, metric_name, metric_type, metric_help, metric_labels, metric_value):
        self.metric_name = self.sanitize_metric_name(metric_name)
        self.metric_type = metric_type
        self.metric_help = metric_help
        self.metric_labels = metric_labels
        self.metric_value = float(metric_value)

    def sanitize_metric_name(self, metric_name: str):
        """Sanitizes Metric Name for Prometheus."""
        metric_name = metric_name.replace(" ", "_")
        metric_name = metric_name.replace("-", "_")
        metric_name = metric_name.replace(".", "_")
        return metric_name.lower()

    def metric_type_string(self, metric_name: str, metric_type: str):
        """Creates Metric Type String for Prometheus."""
        return "# TYPE {} {}\n".format(metric_name, metric_type)

    def metric_help_string(self, metric_name: str, metric_help: str):
        """Creates Metric Help String for Prometheus."""
        return "# HELP  {} {}\n".format(metric_name, metric_help)

    def metric_string(self, metric_name: str, labels: list, metric_value: float):
        """Creates a Metric String for Prometheus."""
        rendered_labels = ", ".join(labels)
        return "{}{{{}}} {}\n".format(metric_name, rendered_labels, metric_value)

    def render(self):
        """Render the full metric block."""
        return (
            self.metric_help_string(self.metric_name, self.metric_help)
            + self.metric_type_string(self.metric_name, self.metric_type)
            + self.metric_string(self.metric_name, self.metric_labels, self.metric_value)
        )
