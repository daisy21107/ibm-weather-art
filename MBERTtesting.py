import torch
import json
import os
from transformers import AutoTokenizer, AutoModel
from torch import nn
import re

# ===== 联合模型定义 =====
# class JointBert(nn.Module):
#     def __init__(self, model_name, num_tags, num_intents):
#         super().__init__()
#         self.bert = AutoModel.from_pretrained(model_name)
#         self.dropout = nn.Dropout(0.1)
#         self.tag_classifier = nn.Linear(self.bert.config.hidden_size, num_tags)
#         self.intent_classifier = nn.Linear(self.bert.config.hidden_size, num_intents)
#
#     def forward(self, input_ids=None, attention_mask=None):
#         outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
#         seq_output = self.dropout(outputs.last_hidden_state)
#         pooled_output = self.dropout(outputs.last_hidden_state[:, 0])
#         tag_logits = self.tag_classifier(seq_output)
#         intent_logits = self.intent_classifier(pooled_output)
#         return tag_logits, intent_logits

class JointBert(nn.Module):
    def __init__(self, model_name, num_tags, num_intents):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(0.1)
        self.tag_head = nn.Linear(self.bert.config.hidden_size, num_tags)     # ✅ 改成 tag_head
        self.intent_head = nn.Linear(self.bert.config.hidden_size, num_intents)  # ✅ 改成 intent_head

    def forward(self, input_ids=None, attention_mask=None):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        seq_output = self.dropout(outputs.last_hidden_state)
        pooled_output = self.dropout(outputs.last_hidden_state[:, 0])
        tag_logits = self.tag_head(seq_output)        # ✅ tag_head
        intent_logits = self.intent_head(pooled_output)  # ✅ intent_head
        return tag_logits, intent_logits

# ===== 标签对齐 =====
def align_word_level_tags(word_ids, tag_ids, id2tag, allowed_tags):
    word_to_tags = {}
    for idx, word_idx in enumerate(word_ids):
        if word_idx is None:
            continue
        tag = id2tag.get(tag_ids[idx], "O")
        if tag not in allowed_tags and tag != "O":
            tag = "O"
        word_to_tags.setdefault(word_idx, []).append(tag)

    pred_tags = []
    for tags in word_to_tags.values():
        tag = next((t for t in tags if t.startswith('B-')),
                   next((t for t in tags if t.startswith('I-')), "O"))
        pred_tags.append(tag)
    return pred_tags

# ===== 文本清洗 =====
def normalize_text(text):
    return re.sub(r"[^a-z0-9\s'\-]", '', text.lower())

# ===== 健壮推理函数 =====
def infer(text, model_dir="joint_model", model_name="google/mobilebert-uncased"):
    try:
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"❌ 模型目录 '{model_dir}' 不存在。")

        # 加载映射文件
        def load_json(file):
            path = os.path.join(model_dir, file)
            if not os.path.exists(path):
                raise FileNotFoundError(f"❌ 缺少文件 {file}，请确认已训练并保存。")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        tag2id = load_json("tag2id.json")
        intent2id = load_json("intent2id.json")
        intent_slot_map = load_json("intent_slot_map.json")

        id2tag = {int(v): k for k, v in tag2id.items()}
        id2intent = {int(v): k for k, v in intent2id.items()}

        tokenizer = AutoTokenizer.from_pretrained(model_name)

        model = JointBert(model_name, num_tags=len(tag2id), num_intents=len(intent2id))
        model_path = os.path.join(model_dir, "pytorch_model.bin")
        if not os.path.exists(model_path):
            raise FileNotFoundError("❌ 找不到模型权重文件 pytorch_model.bin")
        model.load_state_dict(torch.load(model_path, map_location="cpu"))
        model.eval()

        # 文本处理
        text = normalize_text(text)
        words = text.strip().split()
        if not words:
            print("⚠️ 输入为空或无有效词语。")
            return None, []

        inputs = tokenizer(words, is_split_into_words=True, return_tensors="pt", padding=True, truncation=True, max_length=128)
        word_ids = inputs.word_ids()

        with torch.no_grad():
            tag_logits, intent_logits = model(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"])

        intent_id = intent_logits.argmax(dim=-1).item()
        intent = id2intent.get(intent_id, "unknown")

        tag_ids = tag_logits.argmax(dim=-1).squeeze().tolist()
        allowed_tags = set(intent_slot_map.get(intent, []))
        if all(isinstance(t, int) for t in allowed_tags):
            allowed_tags = set(id2tag[t] for t in allowed_tags)

        pred_tags = align_word_level_tags(word_ids, tag_ids, id2tag, allowed_tags)
        return intent, list(zip(words, pred_tags))

    except Exception as e:
        print(f"🚫 推理失败：{e}")
        return None, []

# ===== 测试入口 =====
if __name__ == "__main__":
    while True:
        try:
            text = input("\n🗣 requirement: ").strip()
            if not text:
                continue
            intent, slots = infer(text)
            if intent is None:
                continue
            print(f"\n🎯 intention: {intent}")
            print("📌 labeled:")
            for word, tag in slots:
                print(f"  {word:<12} -> {tag}")
        except KeyboardInterrupt:
            print("\n✅ End。")
            break
