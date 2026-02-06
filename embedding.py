import torch
from transformers import AutoProcessor, AutoModel
from PIL import Image
import requests
from io import BytesIO
import numpy as np
from config import EMBEDDING_MODEL, EMBEDDING_DIM
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class SigLIPEmbedder:
    def __init__(self, model_name=EMBEDDING_MODEL):
        self.model_name = model_name
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Using device: {self.device}")

        # Load model and processor
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    async def generate_embedding_async(self, image_url):
        """Generate embedding asynchronously"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self.generate_embedding, image_url)

    def generate_embedding(self, image_url):
        """Generate 768-dimensional embedding for image URL"""
        try:
            # Download image
            response = requests.get(image_url, timeout=30, stream=True)
            response.raise_for_status()

            # Open image
            image = Image.open(BytesIO(response.content))

            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Resize image to expected size if needed (SigLIP typically expects 384x384 for base-patch16-384)
            image = image.resize((384, 384), Image.Resampling.LANCZOS)

            # Process image - SigLIP requires both image and text
            # Use empty text or a generic description
            text = [""]  # Empty text for image-only embedding
            inputs = self.processor(text=text, images=image, return_tensors="pt", padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate embedding
            with torch.no_grad():
                outputs = self.model(**inputs)
                # For SigLIP, we want the image embeddings (vision model output)
                # The outputs.image_embeds contains the image embeddings
                if hasattr(outputs, 'image_embeds'):
                    embedding = outputs.image_embeds
                elif hasattr(outputs, 'pooler_output'):
                    embedding = outputs.pooler_output
                else:
                    # Fallback to mean pooling
                    embedding = outputs.last_hidden_state.mean(dim=1)

            # Convert to numpy and flatten
            embedding = embedding.cpu().numpy().flatten()

            # Ensure correct dimension
            if len(embedding) != EMBEDDING_DIM:
                logger.warning(f"Embedding dimension mismatch: {len(embedding)} vs {EMBEDDING_DIM}")
                # Pad or truncate if necessary
                if len(embedding) < EMBEDDING_DIM:
                    embedding = np.pad(embedding, (0, EMBEDDING_DIM - len(embedding)))
                else:
                    embedding = embedding[:EMBEDDING_DIM]

            # Normalize the embedding (L2 normalization)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating embedding for {image_url}: {e}")
            return None

    def generate_text_embedding(self, text: str):
        """Generate 768-dimensional text embedding using SigLIP text encoder (same space as image embeddings)."""
        if not text or not text.strip():
            return None
        try:
            # Text only: use processor's tokenizer; padding="max_length" as in SigLIP docs
            inputs = self.processor(
                text=[text.strip()],
                padding="max_length",
                return_tensors="pt",
                truncation=True,
            )
            # get_text_features expects only input_ids and attention_mask (no pixel_values)
            text_inputs = {k: v.to(self.device) for k, v in inputs.items() if k in ("input_ids", "attention_mask")}
            if not text_inputs:
                text_inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                # get_text_features returns pooler_output (projected text embedding, same dim as image_embeds)
                text_output = self.model.get_text_features(**text_inputs)
                embedding = text_output.pooler_output.cpu().numpy().flatten()

            if len(embedding) != EMBEDDING_DIM:
                if len(embedding) < EMBEDDING_DIM:
                    embedding = np.pad(embedding, (0, EMBEDDING_DIM - len(embedding)))
                else:
                    embedding = embedding[:EMBEDDING_DIM]

            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating text embedding: {e}")
            return None

    async def generate_text_embedding_async(self, text: str):
        """Generate text embedding asynchronously."""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self.generate_text_embedding, text)

    def __del__(self):
        """Cleanup GPU memory"""
        if hasattr(self, 'model'):
            del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

# Global embedder instance
_embedder = None

def get_embedder():
    """Get or create global embedder instance"""
    global _embedder
    if _embedder is None:
        _embedder = SigLIPEmbedder()
    return _embedder

async def generate_image_embedding(image_url):
    """Convenience function to generate image embedding."""
    embedder = get_embedder()
    return await embedder.generate_embedding_async(image_url)


async def generate_text_embedding(text: str):
    """Convenience function to generate text embedding (same model as image, for info_embedding)."""
    if not text or not text.strip():
        return None
    embedder = get_embedder()
    return await embedder.generate_text_embedding_async(text)