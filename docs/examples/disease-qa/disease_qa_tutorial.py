# Disease Information App with Sonar API - Interactive Browser App
# ========================================================

# This notebook demonstrates how to build a robust disease information app using Perplexity's AI API
# and generates an HTML file that can be opened in a browser with an interactive UI

# 1. Setup and Dependencies
# ------------------------

import requests
import json
import pandas as pd
from IPython.display import HTML, display, IFrame
import os
import webbrowser
from pathlib import Path
import logging
from dotenv import load_dotenv
from typing import Dict, List, Optional, Union, Any
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("disease_app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("disease_app")

# 2. API Configuration
# -------------------

# Load environment variables from .env file if it exists
load_dotenv()

# Get API key from environment variable or use a placeholder
API_KEY = os.environ.get('PERPLEXITY_API_KEY', 'API_KEY')
API_ENDPOINT = 'https://api.perplexity.ai/chat/completions'

class ApiError(Exception):
    """Custom exception for API-related errors."""
    pass

# 3. Function to Query Perplexity API (for testing in notebook)
# ----------------------------------

def ask_disease_question(question: str, api_key: str = API_KEY, model: str = "sonar-pro") -> Optional[Dict[str, Any]]:
    """
    Send a disease-related question to Perplexity API and parse the response.
    
    Args:
        question: The question about a disease
        api_key: The Perplexity API key (defaults to environment variable)
        model: The model to use for the query (defaults to sonar-pro)
        
    Returns:
        Dictionary with overview, causes, treatments, and citations or None if an error occurs
        
    Raises:
        ApiError: If there's an issue with the API request
    """
    if api_key == 'API_KEY':
        logger.warning("Using placeholder API key. Set PERPLEXITY_API_KEY environment variable.")
    
    # Construct a prompt instructing the API to output only valid JSON
    prompt = f"""
You are a medical assistant. Please answer the following question about a disease and provide only valid JSON output.
The JSON object must have exactly four keys: "overview", "causes", "treatments", and "citations".
For example:
{{
  "overview": "A brief description of the disease.",
  "causes": "The causes of the disease.",
  "treatments": "Possible treatments for the disease.",
  "citations": ["https://example.com/citation1", "https://example.com/citation2"]
}}
Now answer this question:
"{question}"
    """.strip()

    # Build the payload
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        # Make the API request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "api-cookbook/1.0",
            "X-Pplx-Integration": "api-cookbook/1.0",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Sending request to Perplexity API for question: '{question}'")
        response = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=30)
        
        # Check for HTTP errors
        if response.status_code != 200:
            error_msg = f"API request failed with status code {response.status_code}: {response.text}"
            logger.error(error_msg)
            raise ApiError(error_msg)
        
        result = response.json()
        
        # Extract and parse the response
        if result.get("choices") and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            try:
                parsed_data = json.loads(content)
                logger.info("Successfully parsed JSON response")
                
                # Validate expected keys are present
                expected_keys = ["overview", "causes", "treatments", "citations"]
                missing_keys = [key for key in expected_keys if key not in parsed_data]
                
                if missing_keys:
                    logger.warning(f"Response missing expected keys: {missing_keys}")
                
                return parsed_data
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse JSON output from API: {str(e)}"
                logger.error(error_msg)
                logger.debug(f"Raw content: {content}")
                return None
        else:
            logger.error("No answer provided in the response.")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        raise ApiError("Request to Perplexity API timed out. Please try again later.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception: {str(e)}")
        raise ApiError(f"Error communicating with Perplexity API: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise ApiError(f"Unexpected error: {str(e)}")

# 4. Create HTML UI File
# ----------------------

def create_html_ui(api_key: str, output_path: str = "disease_qa.html") -> str:
    """
    Create an HTML file with the disease Q&A interface
    
    Args:
        api_key: The Perplexity API key
        output_path: The path where the HTML file should be saved
    
    Returns:
        The absolute path to the created HTML file
    """
    logger.info(f"Creating HTML UI file at {output_path}")
    
    # Sanitize API key for display in logs
    displayed_key = f"{api_key[:5]}...{api_key[-5:]}" if len(api_key) > 10 else "***"
    logger.info(f"Using API key: {displayed_key}")
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Disease Q&A Knowledge Card</title>
  <style>
    /* Base styling */
    body {{
      font-family: Helvetica, Arial, sans-serif;
      background-color: #F7F7F8; /* Light background */
      color: #333;
      margin: 0;
      padding: 0;
    }}
    .container {{
      max-width: 800px;
      margin: 2rem auto;
      padding: 1rem;
    }}
    h1 {{
      text-align: center;
      color: #111;
      margin-bottom: 1rem;
    }}
    /* Form styling */
    #qaForm {{
      display: flex;
      justify-content: center;
      margin-bottom: 1.5rem;
    }}
    #question {{
      flex: 1;
      padding: 0.75rem;
      font-size: 1.2rem;
      border: 1px solid #ccc;
      border-radius: 4px;
      margin-right: 0.5rem;
    }}
    #askButton {{
      padding: 0.75rem 1rem;
      font-size: 1.2rem;
      background-color: #10a37f; /* Accent color */
      border: none;
      color: #fff;
      border-radius: 4px;
      cursor: pointer;
      transition: background-color 0.2s ease;
    }}
    #askButton:hover {{
      background-color: #0d8a66;
    }}
    #askButton:disabled {{
      background-color: #cccccc;
      cursor: not-allowed;
    }}
    /* Knowledge card and citations styling */
    #knowledgeCard, #citationsCard {{
      background: #fff;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      padding: 1rem;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      margin-top: 1.5rem;
      display: none;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      text-align: left;
      padding: 0.75rem;
      border-bottom: 1px solid #e0e0e0;
    }}
    th {{
      background-color: #fafafa;
      width: 25%;
    }}
    /* Citations list styling */
    #citationsList {{
      list-style-type: disc;
      padding-left: 20px;
    }}
    #citationsList li {{
      margin-bottom: 0.5rem;
    }}
    #citationsList a {{
      color: #10a37f;
      text-decoration: none;
    }}
    #citationsList a:hover {{
      text-decoration: underline;
    }}
    /* Loading overlay styling */
    #loadingOverlay {{
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(255, 255, 255, 0.8);
      display: flex;
      justify-content: center;
      align-items: center;
      z-index: 9999;
      display: none;
    }}
    .spinner {{
      border: 8px solid #f3f3f3;
      border-top: 8px solid #10a37f;
      border-radius: 50%;
      width: 60px;
      height: 60px;
      animation: spin 1s linear infinite;
    }}
    @keyframes spin {{
      0% {{ transform: rotate(0deg); }}
      100% {{ transform: rotate(360deg); }}
    }}
    /* Error message styling */
    #errorMessage {{
      background-color: #ffeaea;
      color: #d32f2f;
      padding: 1rem;
      border-radius: 4px;
      margin: 1rem 0;
      display: none;
    }}
    /* Added footer with tutorial info */
    .footer {{
      text-align: center;
      margin-top: 2rem;
      padding: 1rem;
      font-size: 0.9rem;
      color: #777;
    }}
    /* Responsive adjustments */
    @media (max-width: 600px) {{
      #qaForm {{
        flex-direction: column;
      }}
      #question {{
        margin-right: 0;
        margin-bottom: 0.5rem;
      }}
    }}
  </style>
</head>
<body>
  <!-- Loading Overlay -->
  <div id="loadingOverlay">
    <div class="spinner"></div>
  </div>

  <div class="container">
    <h1>Disease Q&A</h1>
    <form id="qaForm">
      <input type="text" id="question" placeholder="Ask a question about a disease (e.g., 'What is stroke?')" required>
      <button type="submit" id="askButton">Ask</button>
    </form>
    
    <!-- Error message container -->
    <div id="errorMessage"></div>

    <!-- Knowledge card container -->
    <div id="knowledgeCard">
      <h2>Knowledge Card</h2>
      <table>
        <tr>
          <th>Overview</th>
          <td id="overview"></td>
        </tr>
        <tr>
          <th>Causes</th>
          <td id="causes"></td>
        </tr>
        <tr>
          <th>Treatments</th>
          <td id="treatments"></td>
        </tr>
      </table>
    </div>

    <!-- Citations container -->
    <div id="citationsCard">
      <h2>Citations</h2>
      <ul id="citationsList"></ul>
    </div>
    
    <div class="footer">
      <p>Created with <a href="https://docs.perplexity.ai" target="_blank">Perplexity Sonar API</a></p>
      <p><small>Last updated: {datetime.now().strftime("%Y-%m-%d")}</small></p>
    </div>
  </div>

  <script>
    // API key from Python notebook
    const API_KEY = '{api_key}';
    // API endpoint as per Perplexity's documentation
    const API_ENDPOINT = 'https://api.perplexity.ai/chat/completions';
    
    // Cache for previously asked questions
    const questionCache = new Map();

    async function askDiseaseQuestion(question) {{
      // Check if we have a cached response
      if (questionCache.has(question)) {{
        console.log('Using cached response');
        return questionCache.get(question);
      }}
    
      // Construct a prompt instructing the API to output only valid JSON
      const prompt = `
You are a medical assistant. Please answer the following question about a disease and provide only valid JSON output.
The JSON object must have exactly four keys: "overview", "causes", "treatments", and "citations".
For example:
{{
  "overview": "A brief description of the disease.",
  "causes": "The causes of the disease.",
  "treatments": "Possible treatments for the disease.",
  "citations": ["https://example.com/citation1", "https://example.com/citation2"]
}}
Now answer this question:
"${{question}}"
      `.trim();

      // Build the payload
      const payload = {{
        model: 'sonar-pro',
        messages: [
          {{ role: 'user', content: prompt }}
        ]
      }};

      try {{
        const response = await fetch(API_ENDPOINT, {{
          method: 'POST',
          headers: {{
            'Authorization': `Bearer ${{API_KEY}}`,
            'User-Agent': 'api-cookbook/1.0',
            'X-Pplx-Integration': 'api-cookbook/1.0',
            'Content-Type': 'application/json'
          }},
          body: JSON.stringify(payload)
        }});

        if (!response.ok) {{
          const responseText = await response.text();
          throw new Error(`Error: ${{response.status}} - ${{responseText || response.statusText}}`);
        }}

        const result = await response.json();

        // The answer is expected in the first choice's message content
        if (result.choices && result.choices.length > 0) {{
          const content = result.choices[0].message.content;
          try {{
            const structuredOutput = JSON.parse(content);
            
            // Cache the result
            questionCache.set(question, structuredOutput);
            
            return structuredOutput;
          }} catch (jsonErr) {{
            throw new Error('Failed to parse JSON output from API. Raw output: ' + content);
          }}
        }} else {{
          throw new Error('No answer provided in the response.');
        }}
      }} catch (error) {{
        console.error(error);
        throw error;
      }}
    }}

    // Utility to show/hide the loading overlay
    function setLoading(isLoading) {{
      document.getElementById('loadingOverlay').style.display = isLoading ? 'flex' : 'none';
      document.getElementById('askButton').disabled = isLoading;
    }}
    
    // Utility to show/hide error message
    function showError(message) {{
      const errorElement = document.getElementById('errorMessage');
      if (message) {{
        errorElement.textContent = message;
        errorElement.style.display = 'block';
      }} else {{
        errorElement.style.display = 'none';
      }}
    }}

    // Handle form submission
    document.getElementById('qaForm').addEventListener('submit', async (event) => {{
      event.preventDefault();

      // Clear any previous error
      showError(null);
      
      // Hide previous results
      document.getElementById('knowledgeCard').style.display = 'none';
      document.getElementById('citationsCard').style.display = 'none';

      // Show loading overlay
      setLoading(true);

      const question = document.getElementById('question').value.trim();
      
      if (!question) {{
        showError('Please enter a question about a disease.');
        setLoading(false);
        return;
      }}
      
      try {{
        const data = await askDiseaseQuestion(question);
        
        // Update the knowledge card with structured data
        document.getElementById('overview').textContent = data.overview || 'N/A';
        document.getElementById('causes').textContent = data.causes || 'N/A';
        document.getElementById('treatments').textContent = data.treatments || 'N/A';
        document.getElementById('knowledgeCard').style.display = 'block';

        // Update the citations section
        const citationsList = document.getElementById('citationsList');
        citationsList.innerHTML = ''; // Clear previous citations
        if (Array.isArray(data.citations) && data.citations.length > 0) {{
          data.citations.forEach(citation => {{
            const li = document.createElement('li');
            const link = document.createElement('a');
            link.href = citation;
            link.textContent = citation;
            link.target = '_blank';
            link.rel = 'noopener noreferrer'; // Security best practice
            li.appendChild(link);
            citationsList.appendChild(li);
          }});
        }} else {{
          const li = document.createElement('li');
          li.textContent = 'No citations provided.';
          citationsList.appendChild(li);
        }}
        document.getElementById('citationsCard').style.display = 'block';
      }} catch (error) {{
        showError(`Error: ${{error.message}}`);
      }} finally {{
        // Hide loading overlay once done
        setLoading(false);
      }}
    }});
    
    // Initial focus
    document.addEventListener('DOMContentLoaded', () => {{
      document.getElementById('question').focus();
    }});
  </script>
</body>
</html>
"""

    try:
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created directory: {output_dir}")

        # Write the HTML to a file
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        # Get the full path
        full_path = os.path.abspath(output_path)
        logger.info(f"HTML UI file created successfully at: {full_path}")
        
        return full_path
    except Exception as e:
        logger.error(f"Error creating HTML UI file: {str(e)}")
        raise

# 5. Function to Display Results in Notebook (for testing)
# -----------------------------

def display_results(data: Optional[Dict[str, Any]]) -> None:
    """
    Display the results in a structured format within the notebook.
    
    Args:
        data: The parsed JSON data from the API
    """
    if not data:
        logger.warning("No data to display.")
        print("No data to display.")
        return
    
    # Create a DataFrame for the main knowledge card
    df = pd.DataFrame({
        "Category": ["Overview", "Causes", "Treatments"],
        "Information": [
            data.get("overview", "N/A"),
            data.get("causes", "N/A"),
            data.get("treatments", "N/A")
        ]
    })
    
    # Display the knowledge card
    print("\n💡 Knowledge Card:")
    display(df.style.set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#fafafa'), ('color', '#333'), ('font-weight', 'bold')]},
        {'selector': 'td', 'props': [('padding', '10px')]},
    ]))
    
    # Display citations
    print("\n📚 Citations:")
    if data.get("citations") and isinstance(data["citations"], list) and len(data["citations"]) > 0:
        for i, citation in enumerate(data["citations"], 1):
            print(f"{i}. {citation}")
    else:
        print("No citations provided.")

# 6. Function to Launch Browser UI
# -------------------------------

def launch_browser_ui(api_key: str = API_KEY, html_path: str = "disease_qa.html") -> str:
    """
    Generate and open the HTML UI in a web browser.
    
    Args:
        api_key: The Perplexity API key
        html_path: Path to save the HTML file
        
    Returns:
        The path to the created HTML file
    """
    try:
        # Create the HTML file
        full_path = create_html_ui(api_key, html_path)
        
        # Convert to file:// URL format
        file_url = f"file://{full_path}"
        
        # Open in the default web browser
        logger.info(f"Opening browser UI: {file_url}")
        webbrowser.open(file_url)
        
        return full_path
    except Exception as e:
        logger.error(f"Error launching browser UI: {str(e)}")
        raise

# 7. Example Usage
# ---------------

# Example 1: Testing the API in the notebook
def test_api_in_notebook():
    """Tests the API with a direct call in the notebook."""
    print("Example 1: Direct API Call")
    print("-------------------------")
    example_question = "What is diabetes?"
    print(f"Question: {example_question}")
    print("Sending request to Perplexity API...")

    # Uncomment the following lines to make a real API call
    # try:
    #     result = ask_disease_question(example_question)
    #     display_results(result)
    # except ApiError as e:
    #     print(f"API Error: {str(e)}")
    
    print("(API call commented out to avoid using your API quota)")
    print("\n")

# Example 2: Generate HTML file and open in browser
def launch_browser_app():
    """Generates the HTML app and opens it in the browser."""
    print("Example 2: Launching Browser UI")
    print("-----------------------------")
    print("Generating HTML file and opening in browser...")
    
    try:
        # Create and open the HTML file
        path = launch_browser_ui()
        
        print(f"\nHTML file created at: {path}")
        print("\nIf the browser doesn't open automatically, you can manually open the file above.")
        
        # Show a preview in the notebook (not all notebook environments support this)
        try:
            display(HTML(f'<p>Preview of UI (may not work in all environments):</p>'))
            display(IFrame(path, width='100%', height=600))
        except Exception as e:
            logger.warning(f"Failed to display preview: {str(e)}")
            print("Preview not available in this environment.")
    except Exception as e:
        logger.error(f"Error running browser app: {str(e)}")
        print(f"Error: {str(e)}")

# Main execution block
if __name__ == "__main__":
    # Check if API key is set
    if API_KEY == 'API_KEY':
        print("⚠️  Warning: Using placeholder API key")
        print("Please set your API key in the PERPLEXITY_API_KEY environment variable")
        print("or replace 'API_KEY' in the code with your actual key.")
        print("\nContinuing with demonstration mode...\n")
    
    # Run the examples
    test_api_in_notebook()
    launch_browser_app()