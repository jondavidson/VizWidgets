from dask.distributed import Client
from dask import delayed
import importlib
from typing import Callable, List, Dict, Any
from pathlib import Path


class DaskPipeline:
    def __init__(self, output_dir: str, scheduler_address: str, max_retries: int = 3):
        """
        Initialize the Dask pipeline.
        
        :param output_dir: The directory to store output files.
        :param scheduler_address: Address of the Dask scheduler.
        :param max_retries: Number of retries if a task fails.
        """
        self.output_dir = Path(output_dir)
        self.scheduler_address = scheduler_address
        self.max_retries = max_retries
        self.client = Client(scheduler_address)  # Connect to Dask distributed scheduler
        self.tasks = {}  # Store task references
        self.task_dependencies = {}  # Store dependencies between tasks
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def add_task(self, func: Callable, task_name: str, inputs: Dict[str, Any] = None, outputs: Dict[str, Any] = None, 
                 options: Dict[str, Any] = None, depends_on: List[str] = None, resources: Dict[str, Any] = None):
        """
        Add a task to the pipeline.
        
        :param func: The function to run as a task.
        :param task_name: The unique name of the task.
        :param inputs: Input arguments for the task.
        :param outputs: Output arguments for the task.
        :param options: Additional options for the task (e.g., overwrite, cleanup).
        :param depends_on: List of task names this task depends on.
        :param resources: Resources required by the task (e.g., specific worker).
        """
        inputs = inputs or {}
        outputs = outputs or {}
        options = options or {}
        depends_on = depends_on or []
        
        # Build delayed task with dependency resolution
        task_delayed = self._build_task(func, task_name, inputs, outputs, options, depends_on)
        
        # Apply worker restrictions or resources
        if resources:
            task_delayed = task_delayed.persist(resources=resources)
        
        # Store the task in the pipeline
        self.tasks[task_name] = task_delayed

    def _build_task(self, func: Callable, task_name: str, inputs: Dict[str, Any], outputs: Dict[str, Any], 
                    options: Dict[str, Any], depends_on: List[str]):
        """
        Build a delayed task, resolving dependencies and handling inputs/outputs.
        
        :param func: The function to run as a task.
        :param task_name: The unique name of the task.
        :param inputs: Input arguments for the task.
        :param outputs: Output arguments for the task.
        :param options: Additional options for the task.
        :param depends_on: List of task names this task depends on.
        :return: A delayed Dask object representing the task.
        """
        # Resolve dependencies: Replace dependent task results (Delayed) with their actual outputs
        resolved_inputs = {}
        for key, value in inputs.items():
            if isinstance(value, str) and value in self.tasks:  # If input is a task name, use the task's result
                resolved_inputs[key] = self.tasks[value]
            else:
                resolved_inputs[key] = value
        
        # Handle dependent tasks if any
        if depends_on:
            dependent_tasks = [self.tasks[dep] for dep in depends_on]
            task_delayed = delayed(lambda *args: func(**resolved_inputs, **outputs, **options))(*dependent_tasks)
        else:
            task_delayed = delayed(func)(**resolved_inputs, **outputs, **options)
        
        return task_delayed

    def run(self):
        """
        Run all tasks in the pipeline.
        """
        # Compute all tasks in parallel or in sequence (based on dependencies)
        dask.compute(list(self.tasks.values()))

    def shutdown(self):
        """
        Shutdown the Dask client.
        """
        self.client.shutdown()


from pathlib import Path

# Define the functions
def task1(output_path):
    output_file = Path(output_path)
    output_file.touch()  # Simulate writing a file
    return output_file

def task2(input_file):
    print(f"Processing {input_file}")
    # Simulate processing the input file
    return f"Processed {input_file}"

# Create the DaskPipeline
pipeline = DaskPipeline(output_dir="output_dir", scheduler_address="tcp://localhost:8786")

# Add the first task (task1), which generates a file
pipeline.add_task(func=task1, task_name="generate_file", inputs={"output_path": "file.txt"})

# Add the second task (task2), which depends on the output of task1
pipeline.add_task(func=task2, task_name="process_file", inputs={"input_file": "generate_file"}, depends_on=["generate_file"])

# Run the pipeline
pipeline.run()

# Shut down the pipeline
pipeline.shutdown()
