"""
CLIP visual embedder for image similarity search
Generates visual embeddings from images using OpenAI's CLIP model
"""
from typing import Union, List
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel
import logging
import io

logger = logging.getLogger(__name__)


class CLIPEmbedder:
    """Generate visual embeddings from images using CLIP"""
    
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        """
        Initialize the CLIP embedder
        
        Args:
            model_name: HuggingFace CLIP model name
        """
        self.model_name = model_name
        self.model = None
        self.processor = None
        self.embedding_dim = 512  # Dimension for clip-vit-base-patch32
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        

    def _load_model(self):
        """Lazy load the model to avoid loading on import"""
        if self.model is None:
            # Log device being used
            if self.device == 'cuda':
                logger.info(f"GPU detected for CLIP: {torch.cuda.get_device_name(0)}")
            else:
                logger.info("No GPU detected for CLIP, using CPU")
            
            logger.info(f"Loading CLIP model: {self.model_name} on {self.device}")
            # Load model - force low_cpu_mem_usage=False to prevent meta tensor errors on CPU
            try:
                self.model = CLIPModel.from_pretrained(self.model_name, low_cpu_mem_usage=False).to(self.device)
                self.processor = CLIPProcessor.from_pretrained(self.model_name, use_fast=True)
            except Exception as e:
                logger.warning(f"Failed to load CLIP model with default settings: {e}")
                # Fallback: strict CPU load
                self.model = CLIPModel.from_pretrained(self.model_name, low_cpu_mem_usage=False)
                self.processor = CLIPProcessor.from_pretrained(self.model_name, use_fast=True)
                if self.device == 'cuda':
                    self.model = self.model.to(self.device)
            
            logger.info("CLIP model loaded successfully")
    

    def _prepare_image(self, image: Union[str, Image.Image, bytes]) -> Image.Image:
        """
        Prepare image for CLIP processing
        
        Args:
            image: File path, PIL Image, or bytes
            
        Returns:
            PIL Image object
        """
        if isinstance(image, str):
            # Load from file path
            return Image.open(image).convert('RGB')
        elif isinstance(image, bytes):
            # Load from bytes
            return Image.open(io.BytesIO(image)).convert('RGB')
        elif isinstance(image, Image.Image):
            # Already a PIL Image
            return image.convert('RGB')
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")
    
    
    def _create_thumbnail(self, image: Image.Image, size: int = 512) -> Image.Image:
        """
        Create a 512x512 thumbnail with aspect ratio preservation
        
        Args:
            image: PIL Image
            size: Target size (default 512x512)
            
        Returns:
            Resized PIL Image with padding
        """
        # Calculate scaling to fit within size x size
        width, height = image.size
        scale = min(size / width, size / height)
        
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Resize image
        resized = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Create new image with black background
        thumbnail = Image.new('RGB', (size, size), (0, 0, 0))
        
        # Paste resized image centered
        x_offset = (size - new_width) // 2
        y_offset = (size - new_height) // 2
        thumbnail.paste(resized, (x_offset, y_offset))
        
        return thumbnail
    
    def embed_image(self, image: Union[str, Image.Image, bytes], 
                    return_thumbnail: bool = False) -> Union[List[float], tuple]:
        """
        Generate CLIP embedding from an image
        
        Args:
            image: File path, PIL Image, or bytes
            return_thumbnail: If True, also return the 512x512 thumbnail
            
        Returns:
            Embedding vector as list of floats, or (embedding, thumbnail) if return_thumbnail=True
        """
        self._load_model()
        
        # Prepare image
        pil_image = self._prepare_image(image)
        
        # Create thumbnail for consistent processing
        thumbnail = self._create_thumbnail(pil_image)
        
        # Process image through CLIP
        inputs = self.processor(images=thumbnail, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            # Normalize the features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        embedding = image_features.cpu().numpy()[0].tolist()
        
        if return_thumbnail:
            return embedding, thumbnail
        return embedding
    

    def embed_text(self, text: str) -> List[float]:
        """
        Generate CLIP embedding from text
        
        Args:
            text: Text prompt or description
            
        Returns:
            Embedding vector as list of floats
        """
        self._load_model()
        
        # Process text through CLIP
        inputs = self.processor(text=[text], return_tensors="pt", padding=True).to(self.device)
        
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
            # Normalize the features
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        
        embedding = text_features.cpu().numpy()[0].tolist()
        return embedding
    
    
    def embed_batch(self, images: List[Union[str, Image.Image, bytes]], 
                    return_thumbnails: bool = False) -> Union[List[List[float]], tuple]:
        """
        Generate CLIP embeddings for multiple images (more efficient)
        
        Args:
            images: List of file paths, PIL Images, or bytes
            return_thumbnails: If True, also return the thumbnails
            
        Returns:
            List of embedding vectors, or (embeddings, thumbnails) if return_thumbnails=True
        """
        self._load_model()
        
        # Prepare all images
        thumbnails = []
        for img in images:
            pil_image = self._prepare_image(img)
            thumbnail = self._create_thumbnail(pil_image)
            thumbnails.append(thumbnail)
        
        # Process batch through CLIP
        inputs = self.processor(images=thumbnails, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            # Normalize the features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        embeddings = [emb.tolist() for emb in image_features.cpu().numpy()]
        
        if return_thumbnails:
            return embeddings, thumbnails
        return embeddings
    

    def save_thumbnail(self, thumbnail: Image.Image, output_path: str, quality: int = 85):
        """
        Save thumbnail as JPG
        
        Args:
            thumbnail: PIL Image
            output_path: Output file path (should end in .jpg)
            quality: JPG quality (default 85)
        """
        thumbnail.save(output_path, 'JPEG', quality=quality, optimize=True)
