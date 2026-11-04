from datetime import datetime, UTC
import json
import time
from pathlib import Path


class RunManager():
    def __init__(self, client, working_dir, metadata_path=None, run_type="generic"):
        self.client = client
        self.metadata, self.metadata_path = self._init_metadata(working_dir, metadata_path=metadata_path, run_type=run_type)

    def _init_metadata(self, working_dir, metadata_path=None, run_type="generic"):
        if metadata_path:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f), metadata_path

        run_id = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = working_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = run_dir / "meta" / "metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)       
        metadata = {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "run_type": run_type,
            "stages": {},
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        return metadata, metadata_path

    def init_stage(self, stage):
        stage_dir = Path(self.metadata["run_dir"]) / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        if stage not in self.metadata["stages"]:
            self.metadata["stages"][stage] = {
                "status": "initialized"
            }
            self.save()
        return stage_dir

    def register_stage(self, stage, batch_info):
        self.metadata["stages"][stage] = {
            "batch_id": batch_info["batch_id"],
            "input_file_id": batch_info["input_file_id"],
            "status": batch_info["status"],
            "input_path": str(batch_info["input_path"]),
            "output_file_id": None,
            "output_path": None
        }
        self.save()

    def update_stage(self, stage, **kwargs):
        self.metadata["stages"][stage].update(kwargs)
        self.save()

    def get_stage(self, stage):
        return self.metadata["stages"][stage]

    def get_stage_dir(self, stage):
        path = Path(self.metadata["run_dir"]) / stage
        return path

    def get_run_dir(self):
        return self.metadata["run_dir"]

    def retrieve_batch(self, stage, output_filename="output.jsonl"):
        stage_data = self.get_stage(stage)
        batch_info = self.client.get_batch_info(stage_data["batch_id"])

        self.update_stage(stage, status=batch_info["status"])

        if batch_info["status"] == "completed" and batch_info["completed"] == 0:
            print("All requests failed. Fetching error file...")

            error_file_id = batch_info["error_file_id"]
            if error_file_id:
                content = self.client.download_error_file(error_file_id)
                print(content)
            else:
                print("No error_file_id")
                print(batch_info)
            raise ValueError

        elif batch_info["status"] == "failed":
            print("Batch failed. Fetching error file...")

            error_file_id = batch_info["error_file_id"]
            if error_file_id:
                content = self.client.download_error_file(error_file_id)
                print(content)
            else:
                print("No error file id")
                print(batch_info)
            raise RuntimeError("Batch job failed.")
            

        elif batch_info["status"].lower() in {"completed", "job_state_succeeded"}:
            output_path = Path(self.metadata["run_dir"]) / stage / "outputs" / output_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self.client.download_output(batch_info["output_file_id"], output_path)
            self.update_stage(
                stage,
                output_file_id=batch_info["output_file_id"],
                output_path=str(output_path)
            )
            return output_path

        elif batch_info["status"] in {"cancelled", "expired"}:
            raise RuntimeError(f"Batch job ended with status: {batch_info["status"]}")

        elif batch_info["status"] != "completed":
            print(f"Job {stage} not completed. Status: {batch_info["status"]}")

    def batch_polling(self, stage, poll_interval=300, max_attempts=5):
        for i in range(max_attempts):
            print(f"Attempt {i + 1} at retrieving batch for {stage}")
            output = self.retrieve_batch(stage)
            if output:
                return output
            time.sleep(poll_interval)
        print("Too many unsuccessful polls, aborting")
        raise RuntimeError

    def save(self):
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)
