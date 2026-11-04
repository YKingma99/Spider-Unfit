import os

from openai import OpenAI
from openbatch import BatchJobManager, ChatCompletionsRequest
from pydantic import BaseModel


class OpenAIProvider():
    def __init__(self, config: dict):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = config["llm"]["openai"]["model"]
        self.endpoint = config["llm"]["openai"]["api_endpoint"]

    def generate(self, prompt: str, response_format: type[BaseModel] | None) -> type[BaseModel] | str:
        if response_format:
            response = self.client.responses.parse(
                model=self.model,
                input=prompt,
                text_format=response_format
            )
            return response.output_parsed

        response = self.client.responses.create(
            model=self.model,
            input=prompt
        )
        return response.output_text

    def generate_batch(self, prompt, input_instances, batch_dir, output_struct=None):
        batch_file_path = batch_dir / "inputs" / "input.jsonl"
        batch_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.build_batch_file(
            prompt=prompt,
            input_instances=input_instances,
            batch_file_path=batch_file_path,
            output_struct=output_struct
        )
        batch_input_file = self.upload_file(file_path=batch_file_path, purpose="batch")
        batch_job = self.create_batch_job(batch_input_file=batch_input_file)
        return {
            "batch_id": batch_job.id,
            "input_file_id": batch_input_file.id,
            "status": batch_job.status,
            "input_path": batch_file_path,
        }

    def build_batch_file(self, prompt, input_instances, batch_file_path,
                         output_struct=None, logprobs=False):
        common_config = ChatCompletionsRequest(model=self.model, logprobs=logprobs)
        if output_struct:
            common_config.set_output_structure(output_struct)
        manager = BatchJobManager()
        manager.add_templated_instances(
            prompt=prompt,
            common_request=common_config,
            input_instances=input_instances,
            save_file_path=batch_file_path
        )

    def upload_file(self, file_path, purpose=None):
        file = self.client.files.create(
            file=open(file_path, "rb"),
            purpose=purpose
        )
        return file

    def create_batch_job(self, batch_input_file):
        job = self.client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint=self.endpoint,
            completion_window="24h"
        )
        return job

    def get_batch_info(self, batch_id):
        info = self.client.batches.retrieve(batch_id)
        return {
            "batch_id": info.id,
            "status": info.status,
            "output_file_id": info.output_file_id,
            "error_file_id": info.error_file_id,
            "completed": info.request_counts.completed,
        }

    def download_output(self, output_file_id, output_path):
        content = self.client.files.content(file_id=output_file_id)
        with open(output_path, "wb") as f:
            f.write(content.read())

    def download_error_file(self, error_file_id):
        content = self.client.files.content(file_id=error_file_id)
        return content.read().decode()

