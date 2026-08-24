#!/usr/bin/env python3
"""
Fact Checker CLI - A tool to identify false or misleading claims in articles or statements
using Perplexity's Sonar API.
Structured output is disabled by default.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
from pydantic import BaseModel, Field
from newspaper import Article, ArticleException
from requests.exceptions import RequestException


class Claim(BaseModel):
    """Model for representing a single claim and its fact check."""
    claim: str = Field(description="The specific claim extracted from the text")
    rating: str = Field(description="Rating of the claim: TRUE, FALSE, MISLEADING, or UNVERIFIABLE")
    explanation: str = Field(description="Detailed explanation with supporting evidence")
    sources: List[str] = Field(description="List of sources used to verify the claim")


class FactCheckResult(BaseModel):
    """Model for the complete fact check result."""
    overall_rating: str = Field(description="Overall rating: MOSTLY_TRUE, MIXED, or MOSTLY_FALSE")
    summary: str = Field(description="Brief summary of the overall findings")
    claims: List[Claim] = Field(description="List of specific claims and their fact checks")


class FactChecker:
    """A class to interact with Perplexity Sonar API for fact checking."""

    API_URL = "https://api.perplexity.ai/chat/completions"
    DEFAULT_MODEL = "sonar-pro"
    PROMPT_FILE = "system_prompt.md"
    
    # Models that support structured outputs (ensure your tier has access)
    STRUCTURED_OUTPUT_MODELS = ["sonar", "sonar-pro", "sonar-reasoning", "sonar-reasoning-pro"]

    def __init__(self, api_key: Optional[str] = None, prompt_file: Optional[str] = None):
        """
        Initialize the FactChecker with API key and system prompt.

        Args:
            api_key: Perplexity API key. If None, will try to read from file or environment.
            prompt_file: Path to file containing the system prompt. If None, uses default.
        """
        self.api_key = api_key or self._get_api_key()
        if not self.api_key:
            raise ValueError(
                "API key not found. Please provide via argument, environment variable, or key file."
            )
        
        self.system_prompt = self._load_system_prompt(prompt_file or self.PROMPT_FILE)

    def _get_api_key(self) -> str:
        """
        Try to get API key from environment or from a file in the current directory.

        Returns:
            The API key if found, empty string otherwise.
        """
        api_key = os.environ.get("PPLX_API_KEY", "")
        if api_key:
            return api_key

        for key_file in ["pplx_api_key", ".pplx_api_key", "PPLX_API_KEY", ".PPLX_API_KEY"]:
            key_path = Path(key_file)
            if key_path.exists():
                try:
                    return key_path.read_text().strip()
                except Exception:
                    pass

        return ""
    
    def _load_system_prompt(self, prompt_file: str) -> str:
        """
        Load the system prompt from a file.

        Args:
            prompt_file: Path to the file containing the system prompt

        Returns:
            The system prompt as a string
        """
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"Warning: Prompt file not found at {prompt_file}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not load system prompt from {prompt_file}: {e}", file=sys.stderr)
            print("Using default system prompt.", file=sys.stderr)
            return (
                "You are a professional fact-checker with extensive research capabilities. "
                "Your task is to evaluate claims or articles for factual accuracy. "
                "Focus on identifying false, misleading, or unsubstantiated claims."
            )

    def check_claim(self, text: str, model: str = DEFAULT_MODEL, use_structured_output: bool = False) -> Dict[str, Any]:
        """
        Check the factual accuracy of a claim or article.

        Args:
            text: The claim or article text to fact check
            model: The Perplexity model to use
            use_structured_output: Whether to use structured output API (if model supports it)

        Returns:
            The parsed response containing fact check results.
        """
        if not text or not text.strip():
            return {"error": "Input text is empty. Cannot perform fact check."}
        user_prompt = f"Fact check the following text and identify any false or misleading claims:\n\n{text}"

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "api-cookbook/1.0",
            "X-Pplx-Integration": "api-cookbook/1.0"
        }

        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }

        can_use_structured_output = model in self.STRUCTURED_OUTPUT_MODELS and use_structured_output
        if can_use_structured_output:
            data["response_format"] = {
                "type": "json_schema",
                "json_schema": {"schema": FactCheckResult.model_json_schema()},
            }

        try:
            response = requests.post(self.API_URL, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            
            citations = result.get("citations", [])
            
            if "choices" in result and result["choices"] and "message" in result["choices"][0]:
                content = result["choices"][0]["message"]["content"]
                
                if can_use_structured_output:
                    try:
                        parsed = json.loads(content)
                        if citations and "citations" not in parsed:
                            parsed["citations"] = citations
                        return parsed
                    except json.JSONDecodeError as e:
                        return {"error": f"Failed to parse structured output: {str(e)}", "raw_response": content, "citations": citations}
                else:
                    parsed = self._parse_response(content)
                    if citations and "citations" not in parsed:
                        parsed["citations"] = citations
                    return parsed
            
            return {"error": "Unexpected API response format", "raw_response": result}
            
        except requests.exceptions.RequestException as e:
            return {"error": f"API request failed: {str(e)}"}
        except json.JSONDecodeError:
            return {"error": "Failed to parse API response as JSON"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """
        Parse the response content to extract JSON if possible.
        If not, fall back to extracting citations from the text.

        Args:
            content: The response content from the API

        Returns:
            A dictionary with parsed JSON fields or with a fallback containing raw response and extracted citations.
        """
        try:
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
                return json.loads(json_content)
            elif "```" in content:
                json_content = content.split("```")[1].split("```")[0].strip()
                return json.loads(json_content)
            else:
                return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            citations = re.findall(r"Sources?:\s*(.+)", content)
            return {
                "raw_response": content,
                "extracted_citations": citations if citations else "No citations found"
            }


def display_results(results: Dict[str, Any], format_json: bool = False):
    """
    Display the fact checking results in a human-readable format.

    Args:
        results: The fact checking results dictionary
        format_json: Whether to display the results as formatted JSON
    """
    if "error" in results:
        print(f"Error: {results['error']}")
        if "raw_response" in results:
            print("\nRaw response:")
            print(results["raw_response"])
        return

    if format_json:
        print(json.dumps(results, indent=2))
        return

    if "overall_rating" in results:
        citation_list = results.get("citations", [])
        if citation_list and "claims" in results:
            for claim in results["claims"]:
                updated_sources = []
                for source in claim.get("sources", []):
                    m = re.match(r"\[(\d+)\]", source.strip())
                    if m:
                        idx = int(m.group(1)) - 1
                        if 0 <= idx < len(citation_list):
                            updated_sources.append(citation_list[idx])
                        else:
                            updated_sources.append(source)
                    else:
                        updated_sources.append(source)
                claim["sources"] = updated_sources

        overall_rating = results["overall_rating"]
        rating_emoji = "🟢" if overall_rating == "MOSTLY_TRUE" else "🟠" if overall_rating == "MIXED" else "🔴"
        print(f"\n{rating_emoji} OVERALL RATING: {overall_rating}")
    
        if "summary" in results:
            print(f"\n📝 SUMMARY:\n{results['summary']}\n")
    
        if "claims" in results:
            print("🔍 CLAIMS ANALYSIS:")
            for i, claim in enumerate(results["claims"], 1):
                rating = claim.get("rating", "UNKNOWN")
                if rating == "TRUE":
                    rating_emoji = "✅"
                elif rating == "FALSE":
                    rating_emoji = "❌"
                elif rating == "MISLEADING":
                    rating_emoji = "⚠️"
                elif rating == "UNVERIFIABLE":
                    rating_emoji = "❓"
                else:
                    rating_emoji = "🔄"
                
                print(f"\nClaim {i}: {rating_emoji} {rating}")
                print(f"  Statement: \"{claim.get('claim', 'No claim text')}\"")
                print(f"  Explanation: {claim.get('explanation', 'No explanation provided')}")
                
                if "sources" in claim and claim["sources"]:
                    print(f"  Sources:")
                    for source in claim["sources"]:
                        print(f"    - {source}")
    
    elif "raw_response" in results:
        print("Response:")
        print(results["raw_response"])
        if "extracted_citations" in results:
            print("\nExtracted Citations:")
            if isinstance(results["extracted_citations"], list):
                for citation in results["extracted_citations"]:
                    print(f"  - {citation}")
            else:
                print(f"  {results['extracted_citations']}")
    
    if "citations" in results:
        print("\nCitations:")
        for citation in results["citations"]:
            print(f"  - {citation}")


def main():
    """Main entry point for the fact checker CLI."""
    parser = argparse.ArgumentParser(
        description="Fact Checker CLI - Identify false or misleading claims in text using Perplexity Sonar API"
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-t", "--text", type=str, help="Text to fact check")
    input_group.add_argument("-f", "--file", type=str, help="Path to file containing text to fact check")
    input_group.add_argument("-u", "--url", type=str, help="URL of the article to fact check")
    
    parser.add_argument(
        "-m",
        "--model", 
        type=str, 
        default=FactChecker.DEFAULT_MODEL,
        help=f"Perplexity model to use (default: {FactChecker.DEFAULT_MODEL})"
    )
    parser.add_argument(
        "-k", 
        "--api-key", 
        type=str, 
        help="Perplexity API key (if not provided, will look for environment variable or key file)"
    )
    parser.add_argument(
        "-p", 
        "--prompt-file", 
        type=str, 
        help=f"Path to file containing the system prompt (default: {FactChecker.PROMPT_FILE})"
    )
    parser.add_argument(
        "-j", 
        "--json", 
        action="store_true", 
        help="Output results as JSON"
    )
    parser.add_argument(
        "--structured-output", 
        action="store_true", 
        help="Enable structured output format (default is non-structured output)"
    )
    
    args = parser.parse_args()
    
    try:
        fact_checker = FactChecker(api_key=args.api_key, prompt_file=args.prompt_file)
        
        if args.file:
            try:
                with open(args.file, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                print(f"Error reading file: {e}", file=sys.stderr)
                return 1
        elif args.url:
            try:
                print(f"Fetching content from URL: {args.url}", file=sys.stderr)
                response = requests.get(args.url, timeout=15) # Add a timeout
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                
                article = Article(url=args.url)
                article.download(input_html=response.text)
                article.parse()
                text = article.text
                if not text:
                    print(f"Error: Could not extract text from URL: {args.url}", file=sys.stderr)
                    return 1
            except RequestException as e:
                print(f"Error fetching URL: {e}", file=sys.stderr)
                return 1
            except ArticleException as e:
                 print(f"Error parsing article content: {e}", file=sys.stderr)
                 return 1
            except Exception as e: # Catch other potential errors during fetch/parse
                print(f"An unexpected error occurred while processing the URL: {e}", file=sys.stderr)
                return 1
        else: # This corresponds to args.text
            text = args.text

        if not text: # Ensure text is not empty before proceeding
             print("Error: No text found to fact check.", file=sys.stderr)
             return 1

        print("Fact checking in progress...", file=sys.stderr)
        results = fact_checker.check_claim(
            text, 
            model=args.model, 
            use_structured_output=args.structured_output
        )
        display_results(results, format_json=args.json)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
