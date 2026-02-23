from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

class LLMEngine:
    def __init__(self):
        model="nvidia/personaplex-7b-v1"
        self.tokenizer=AutoTokenizer.from_pretrained(model)
        self.model=AutoModelForCausalLM.from_pretrained(model,device_map="auto")

    def generate_response(self,user_input,intent,context=None):
        prompt=f"Memory:{context}\nUser:{user_input}\nAssistant:"
        inputs=self.tokenizer(prompt,return_tensors="pt").to(self.model.device)
        out=self.model.generate(**inputs,max_new_tokens=120)
        return self.tokenizer.decode(out[0],skip_special_tokens=True)