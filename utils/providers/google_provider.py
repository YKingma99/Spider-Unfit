import os
import json
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel

from utils.utils import remove_defs_and_refs


class GoogleProvider():
    def __init__(self, config: dict):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = config["llm"]["google"]["model"]

    def generate(
        self,
        prompt: str,
        response_format: type[BaseModel] | None = None,
        tools=None,
    ) -> type[BaseModel] | str:
        config_kwargs = {}

        if response_format is not None:
            config_kwargs["response_schema"] = response_format

        if tools is not None:
            config_kwargs["tools"] = tools

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        return response

    def generate_batch(
        self,
        prompt,
        input_instances,
        batch_dir,
        output_struct=None,
    ):
        batch_file_path = batch_dir / "inputs" / "input.jsonl"
        batch_file_path.parent.mkdir(parents=True, exist_ok=True)

        self.build_batch_file(
            prompt=prompt,
            input_instances=input_instances,
            batch_file_path=batch_file_path,
            output_struct=output_struct,
        )

        uploaded_file = self.upload_file(batch_file_path)

        batch_job = self.create_batch_job(uploaded_file)
        
        return {
            "batch_id": batch_job.name.lower(),
            "input_file_id": uploaded_file.name,
            "status": batch_job.state.name.lower(),
            "input_path": batch_file_path
        }

    def build_batch_file(self, prompt, input_instances, batch_file_path, output_struct=None):
        with open(batch_file_path, "w", encoding="utf-8") as f:
            requests = [
                {
                    "key": instance["key"], 
                    "request": {"contents": [{
                        "parts": [{"text": prompt.messages[0].content.format(**instance["prompt_value_mapping"])}],
                        'role': "user"
                    },
                        {"parts": [{"text": prompt.messages[1].content.format(**instance["prompt_value_mapping"])}],
                        'role': "user"
                        },
                        ],
                        'generation_config': {
                            'response_mime_type': 'application/json',
                            'response_schema': remove_defs_and_refs(output_struct.model_json_schema()),
                        }
                    }
                } for instance in input_instances
            ]

            for req in requests:
                f.write(json.dumps(req) + "\n")
            
    def upload_file(self, file_path, purpose=None):
        uploaded_file = self.client.files.upload(
            file=file_path,
            config=types.UploadFileConfig(display_name=str(file_path), mime_type='jsonl')
        )
        return uploaded_file
    
    def create_batch_job(self, batch_input_file):
        job = self.client.batches.create(
            model=self.model,
            src=batch_input_file.name,
            config={
                "display_name": batch_input_file.name,
            },
        )
        return job
    
    def get_batch_info(self, batch_id):
        info = self.client.batches.get(name=batch_id)
        if info.state.name.lower() == "job_state_succeeded":
            return {
                "batch_id": info.name.lower(),
                "status": info.state.name.lower(),
                "output_file_id": info.dest.file_name,
                "error_file_id": info.dest.file_name,
                "completed": info.completion_stats,
            }
        else:
            return {
                "batch_id": info.name.lower(),
                "status": info.state.name.lower(),
                "output_file_id": None,
                "error_file_id": None,
                "completed": None,
            }

    def download_output(self, output_file_id, output_path):
        file_content = self.client.files.download(file=output_file_id)
        with open(output_path, "wb") as f:
            f.write(file_content)

    def download_error_file(self, error_file_id):
        file_content = self.client.files.download(file=error_file_id)
        return file_content.decode("utf-8")
