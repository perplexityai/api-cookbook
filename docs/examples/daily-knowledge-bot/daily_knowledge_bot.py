#!/usr/bin/env python3
"""
Daily Knowledge Bot

This script uses the Perplexity API to fetch an interesting fact about a rotating
topic each day. It can be scheduled to run daily using cron or Task Scheduler.

Usage:
  python daily_knowledge_bot.py

Requirements:
  - requests
  - python-dotenv
"""

import os
import json
import logging
import sys
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("daily_knowledge_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("daily_knowledge_bot")


class ConfigurationError(Exception):
    """Exception raised for errors in the configuration."""
    pass


class PerplexityClient:
    """Client for interacting with the Perplexity API."""
    
    BASE_URL = "https://api.perplexity.ai/chat/completions"
    
    def __init__(self, api_key: str):
        """
        Initialize the Perplexity API client.
        
        Args:
            api_key: API key for authentication
        """
        if not api_key:
            raise ConfigurationError("Perplexity API key is required")
        
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "api-cookbook/1.0",
            "X-Pplx-Integration": "api-cookbook/1.0",
            "Content-Type": "application/json"
        }
    
    def get_fact(self, topic: str, max_tokens: int = 150, temperature: float = 0.7) -> str:
        """
        Fetch an interesting fact about the given topic.
        
        Args:
            topic: The topic to get a fact about
            max_tokens: Maximum number of tokens in the response
            temperature: Controls randomness (0-1)
            
        Returns:
            An interesting fact about the topic
            
        Raises:
            requests.exceptions.RequestException: If API request fails
        """
        data = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides interesting, accurate, and concise facts. Respond with only one fascinating fact, kept under 100 words."
                },
                {
                    "role": "user",
                    "content": f"Tell me an interesting fact about {topic} that most people don't know."
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        response = requests.post(self.BASE_URL, headers=self.headers, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


class DailyFactService:
    """Service to manage retrieval and storage of daily facts."""
    
    def __init__(self, client: PerplexityClient, output_dir: Path = None):
        """
        Initialize the daily fact service.
        
        Args:
            client: Perplexity API client
            output_dir: Directory to save fact files
        """
        self.client = client
        self.output_dir = output_dir or Path.cwd()
        self.output_dir.mkdir(exist_ok=True)
        
        # Default topics
        self.topics = [
            "astronomy", 
            "history", 
            "biology", 
            "technology", 
            "psychology",
            "ocean life",
            "ancient civilizations",
            "quantum physics",
            "art history",
            "culinary science"
        ]
    
    def load_topics_from_file(self, filepath: Union[str, Path]) -> None:
        """
        Load topics from a configuration file.
        
        Args:
            filepath: Path to the topics file (one topic per line)
        """
        try:
            topics_file = Path(filepath)
            if topics_file.exists():
                with open(topics_file, "r") as f:
                    topics = [line.strip() for line in f if line.strip()]
                
                if topics:
                    self.topics = topics
                    logger.info(f"Loaded {len(topics)} topics from {filepath}")
                else:
                    logger.warning(f"No topics found in {filepath}, using defaults")
            else:
                logger.warning(f"Topics file {filepath} not found, using defaults")
        except Exception as e:
            logger.error(f"Error loading topics file: {e}")
    
    def get_daily_topic(self) -> str:
        """
        Select a topic for today.
        
        Returns:
            The selected topic
        """
        day = datetime.now().day
        # Prevent index errors with modulo and ensure we don't get -1 on the last day
        topic_index = day % len(self.topics)
        if topic_index == 0 and len(self.topics) > 0:
            topic_index = len(self.topics) - 1
        else:
            topic_index -= 1
            
        return self.topics[topic_index]
    
    def get_random_topic(self) -> str:
        """
        Select a random topic as a fallback.
        
        Returns:
            A randomly selected topic
        """
        return random.choice(self.topics)
    
    def get_and_save_daily_fact(self) -> Dict[str, str]:
        """
        Get today's fact and save it to a file.
        
        Returns:
            Dictionary with topic, fact, and file information
        """
        # Try to get the daily topic, fall back to random if there's an error
        try:
            topic = self.get_daily_topic()
        except Exception as e:
            logger.error(f"Error getting daily topic: {e}")
            topic = self.get_random_topic()
        
        logger.info(f"Getting today's fact about: {topic}")
        
        try:
            fact = self.client.get_fact(topic)
            
            # Save the fact
            timestamp = datetime.now().strftime("%Y-%m-%d")
            filename = self.output_dir / f"daily_fact_{timestamp}.txt"
            
            with open(filename, "w") as f:
                f.write(f"DAILY FACT - {timestamp}\n")
                f.write(f"Topic: {topic}\n\n")
                f.write(fact)
            
            logger.info(f"Fact saved to {filename}")
            
            return {
                "topic": topic,
                "fact": fact,
                "filename": str(filename)
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise


def load_config() -> Dict[str, str]:
    """
    Load configuration from environment variables or .env file.
    
    Returns:
        Dictionary of configuration values
    """
    # Load environment variables from .env file if present
    load_dotenv()
    
    # Get API key from environment variables
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    
    # Get output directory from environment variables or use default
    output_dir = os.environ.get("OUTPUT_DIR", "./facts")
    
    # Get topics file path from environment variables
    topics_file = os.environ.get("TOPICS_FILE", "./topics.txt")
    
    return {
        "api_key": api_key,
        "output_dir": output_dir,
        "topics_file": topics_file
    }


def main():
    """Main function that runs the daily knowledge bot."""
    try:
        # Load configuration
        config = load_config()
        
        # Validate API key
        if not config["api_key"]:
            logger.error("API key is required. Set PERPLEXITY_API_KEY environment variable or add it to .env file.")
            sys.exit(1)
        
        # Initialize API client
        client = PerplexityClient(config["api_key"])
        
        # Create output directory
        output_dir = Path(config["output_dir"])
        output_dir.mkdir(exist_ok=True)
        
        # Initialize service
        fact_service = DailyFactService(client, output_dir)
        
        # Load custom topics if available
        if config["topics_file"]:
            fact_service.load_topics_from_file(config["topics_file"])
        
        # Get and save today's fact
        result = fact_service.get_and_save_daily_fact()
        
        # Display the results
        print(f"\nToday's {result['topic']} fact: {result['fact']}")
        print(f"Saved to: {result['filename']}")
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logger.error(f"API communication error: {e}")
        sys.exit(2)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()