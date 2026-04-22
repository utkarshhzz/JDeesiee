# generating 8k+ synthetic candidates using faker 
# defines 25+ roles x 200+ industries  also build fake resume.text
# also abtch insert into supabase

# as on conflict do nothing so rerun wont do any issue
import asyncio
import hashlib
import json
import random
import sys
import uuid
from pathlib import Path
from faker import Faker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tqdm import tqdm


# ── Setup Python path ────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings
from app.core.logging import setup_logging
import structlog
setup_logging(debug=True)
logger = structlog.get_logger()

# ── Faker instances for different locales 
# We want realistic names from different countries.
# Faker("en_IN") generates Indian names, Faker("en_US") generates American names.
# This makes the data look real in the Supabase Table Editor.
fake = Faker(["en_IN", "en_US", "en_GB", "en_AU", "en_CA"])
Faker.seed(42)       # Reproducible results — same data every run
random.seed(42)

TARGET_COUNT=8100

INDUSTRY_ROLES: dict[str, list[str]] = {
    # Software and tech
    "Software Engineering": [
        "Software Engineer", "Senior Software Engineer", "Staff Engineer",
        "Principal Engineer", "Engineering Manager", "VP of Engineering",
        "Frontend Developer", "Backend Developer", "Full Stack Developer",
        "Mobile Developer", "iOS Developer", "Android Developer",
        "Embedded Systems Engineer", "Firmware Engineer",
    ],
    "DevOps & Infrastructure": [
        "DevOps Engineer", "Site Reliability Engineer", "Platform Engineer",
        "Cloud Architect", "Infrastructure Engineer", "Systems Administrator",
        "Release Engineer", "Build Engineer", "Cloud Engineer",
    ],
    "Data Engineering": [
        "Data Engineer", "Senior Data Engineer", "ETL Developer",
        "Data Architect", "Analytics Engineer", "Data Platform Engineer",
        "Big Data Engineer", "Streaming Engineer",
    ],
    "Data Science & ML": [
        "Data Scientist", "Senior Data Scientist", "ML Engineer",
        "AI Engineer", "Research Scientist", "Applied Scientist",
        "NLP Engineer", "Computer Vision Engineer", "MLOps Engineer",
        "Deep Learning Engineer", "AI Research Lead",
    ],
    "Cybersecurity": [
        "Security Engineer", "Security Analyst", "Penetration Tester",
        "SOC Analyst", "Cloud Security Engineer", "AppSec Engineer",
        "Security Architect", "CISO", "Threat Intelligence Analyst",
        "Identity & Access Management Engineer",
    ],
    "QA & Testing": [
        "QA Engineer", "Senior QA Engineer", "SDET",
        "Automation Test Engineer", "Performance Test Engineer",
        "QA Lead", "Test Manager", "Manual Tester",
    ],
    "Cloud & Networking": [
        "Cloud Solutions Architect", "Network Engineer",
        "Network Security Engineer", "Wireless Engineer",
        "Cloud Consultant", "Cloud Migration Specialist",
    ],

    # Product and design
    "Product Management": [
        "Product Manager", "Senior Product Manager", "Group PM",
        "VP of Product", "Technical Product Manager",
        "Associate Product Manager", "Product Owner",
    ],
    "UI/UX Design": [
        "UX Designer", "UI Designer", "Product Designer",
        "UX Researcher", "Interaction Designer", "Visual Designer",
        "Design Lead", "Head of Design",
    ],

    # ── Business & Operations ────────────────────────────────────────
    "Business & Strategy": [
        "Business Analyst", "Management Consultant",
        "Strategy Analyst", "Operations Manager",
        "Business Development Manager", "Growth Manager",
    ],
    "Sales & Marketing": [
        "Digital Marketing Manager", "SEO Specialist",
        "Content Marketing Manager", "Growth Hacker",
        "Sales Engineer", "Account Executive",
        "Marketing Analyst", "Brand Manager",
    ],
    "Human Resources": [
        "HR Manager", "Technical Recruiter", "Talent Acquisition Lead",
        "People Operations Manager", "HR Business Partner",
        "Compensation Analyst", "L&D Specialist",
    ],
    # ── Finance & Banking ────────────────────────────────────────────
    "Finance & FinTech": [
        "Financial Analyst", "Quantitative Analyst",
        "Risk Analyst", "FinTech Developer",
        "Blockchain Developer", "Payment Systems Engineer",
        "Treasury Analyst", "Credit Risk Modeler",
    ],
    # ── Healthcare ───────────────────────────────────────────────────
    "Healthcare IT": [
        "Health Informatics Specialist", "Clinical Data Analyst",
        "EHR Implementation Specialist", "Bioinformatics Engineer",
        "Healthcare Software Developer", "Medical Device Engineer",
        "Telemedicine Developer",
    ],
    # ── E-Commerce & Retail ──────────────────────────────────────────
    "E-Commerce & Retail": [
        "E-Commerce Developer", "Shopify Developer",
        "Supply Chain Analyst", "Inventory Analyst",
        "Marketplace Engineer", "Recommendation Engine Engineer",
    ],
    # ── Education & EdTech ───────────────────────────────────────────
    "EdTech": [
        "EdTech Developer", "Instructional Designer",
        "LMS Administrator", "Curriculum Developer",
        "Educational Data Analyst",
    ],
    # ── Gaming ───────────────────────────────────────────────────────
    "Gaming & Entertainment": [
        "Game Developer", "Unity Developer", "Unreal Engine Developer",
        "Game Designer", "Graphics Programmer",
        "Technical Artist", "VR/AR Developer",
    ],
    # ── Telecom ──────────────────────────────────────────────────────
    "Telecom": [
        "Telecom Engineer", "RF Engineer", "5G Network Engineer",
        "OSS/BSS Developer", "VoIP Engineer",
    ],
    # ── Media & Content ──────────────────────────────────────────────
    "Media & Content": [
        "Content Writer", "Technical Writer", "Video Editor",
        "Streaming Platform Engineer", "CMS Developer",
    ],
    # ── Legal Tech ───────────────────────────────────────────────────
    "Legal Tech": [
        "Legal Tech Developer", "Contract Analyst",
        "Compliance Engineer", "RegTech Developer",
    ],
    # ── Construction & Real Estate ───────────────────────────────────
    "Construction & PropTech": [
        "BIM Engineer", "PropTech Developer",
        "GIS Analyst", "Smart Building Engineer",
    ],
    # ── Energy & CleanTech ───────────────────────────────────────────
    "Energy & CleanTech": [
        "Energy Data Analyst", "IoT Engineer",
        "SCADA Engineer", "Renewable Energy Developer",
        "Smart Grid Engineer",
    ],
    # ── Logistics & Supply Chain ─────────────────────────────────────
    "Logistics & Supply Chain": [
        "Supply Chain Developer", "Logistics Analyst",
        "Route Optimization Engineer", "Warehouse Automation Engineer",
    ],
    # ── Government & GovTech ─────────────────────────────────────────
    "Government & GovTech": [
        "GovTech Developer", "Public Sector Analyst",
        "Digital Transformation Specialist", "e-Governance Architect",
    ],
    # ── Automotive ───────────────────────────────────────────────────
    "Automotive & Mobility": [
        "ADAS Engineer", "Autonomous Vehicle Engineer",
        "Connected Car Developer", "Telematics Engineer",
        "EV Battery Management Developer",
    ],



}


# role to skills maping each role has pool of relevant skills 
# eg data scientise should have python pandas not react neccesary


ROLE_SKILLS: dict[str, list[str]] = {
    # Software
    "Software Engineer":       ["Python", "Java", "Go", "REST", "SQL", "Docker", "Git", "Microservices", "PostgreSQL", "Redis"],
    "Senior Software Engineer":["Python", "Java", "Go", "Kubernetes", "AWS", "System Design", "Microservices", "PostgreSQL", "CI/CD", "Kafka"],
    "Staff Engineer":          ["System Design", "Python", "Go", "Kubernetes", "AWS", "Architecture", "Mentoring", "Kafka", "gRPC"],
    "Principal Engineer":      ["Architecture", "System Design", "Cloud", "Leadership", "Microservices", "Kubernetes", "AWS", "Mentoring"],
    "Engineering Manager":     ["Leadership", "Agile", "Scrum", "Python", "System Design", "Hiring", "Team Management", "JIRA"],
    "VP of Engineering":       ["Leadership", "Strategy", "Architecture", "Cloud", "Team Management", "Budgeting", "Agile"],
    "Frontend Developer":      ["React", "TypeScript", "JavaScript", "HTML", "CSS", "Redux", "Next.js", "Tailwind CSS", "Webpack", "Figma"],
    "Backend Developer":       ["Python", "Node.js", "PostgreSQL", "Redis", "Docker", "REST", "FastAPI", "Kafka", "MongoDB"],
    "Full Stack Developer":    ["React", "Node.js", "TypeScript", "PostgreSQL", "Docker", "REST", "MongoDB", "Git", "AWS"],
    "Mobile Developer":        ["React Native", "Flutter", "TypeScript", "REST", "Firebase", "Git", "iOS", "Android"],
    "iOS Developer":           ["Swift", "iOS", "Xcode", "UIKit", "SwiftUI", "Core Data", "REST", "Git"],
    "Android Developer":       ["Kotlin", "Android", "Jetpack Compose", "REST", "Firebase", "Git", "Java"],
    "Embedded Systems Engineer":["C", "C++", "RTOS", "Embedded Linux", "ARM", "I2C", "SPI", "UART"],
    "Firmware Engineer":       ["C", "C++", "RTOS", "ARM", "Embedded", "Debugging", "Assembly"],
    # DevOps
    "DevOps Engineer":         ["Docker", "Kubernetes", "Terraform", "AWS", "CI/CD", "Jenkins", "Linux", "Ansible", "Prometheus", "Grafana"],
    "Site Reliability Engineer":["Kubernetes", "Prometheus", "Grafana", "Python", "Go", "AWS", "Linux", "Terraform", "Incident Management"],
    "Platform Engineer":       ["Kubernetes", "Terraform", "AWS", "Docker", "CI/CD", "Go", "ArgoCD", "Helm"],
    "Cloud Architect":         ["AWS", "Azure", "GCP", "Terraform", "Architecture", "Kubernetes", "Security", "Networking"],
    "Infrastructure Engineer": ["Linux", "AWS", "Terraform", "Ansible", "Networking", "Docker", "Monitoring"],
    "Systems Administrator":   ["Linux", "Windows Server", "Networking", "Active Directory", "VMware", "Bash", "PowerShell"],
    "Release Engineer":        ["CI/CD", "Jenkins", "Git", "Docker", "Scripting", "Python", "Bash"],
    "Build Engineer":          ["CI/CD", "Jenkins", "Maven", "Gradle", "Docker", "Git", "Bash"],
    "Cloud Engineer":          ["AWS", "Azure", "GCP", "Terraform", "Docker", "Kubernetes", "Python", "CloudFormation"],
    # Data Engineering
    "Data Engineer":           ["Python", "SQL", "Spark", "Airflow", "AWS", "PostgreSQL", "ETL", "Kafka", "dbt", "Snowflake"],
    "Senior Data Engineer":    ["Python", "Spark", "Kafka", "Airflow", "AWS", "Snowflake", "dbt", "Data Pipeline", "Terraform"],
    "ETL Developer":           ["SQL", "Python", "SSIS", "Informatica", "ETL", "Data Pipeline", "Oracle", "PostgreSQL"],
    "Data Architect":          ["SQL", "Data Modeling", "Snowflake", "BigQuery", "AWS", "Architecture", "ETL", "PostgreSQL"],
    "Analytics Engineer":      ["SQL", "dbt", "Python", "Snowflake", "Looker", "BigQuery", "Data Modeling", "Git"],
    "Data Platform Engineer":  ["Spark", "Kafka", "Airflow", "Python", "AWS", "Terraform", "Docker", "Kubernetes"],
    "Big Data Engineer":       ["Hadoop", "Spark", "Hive", "Kafka", "Python", "Scala", "AWS", "Data Pipeline"],
    "Streaming Engineer":      ["Kafka", "Flink", "Spark Streaming", "Python", "AWS", "Docker", "Real-time"],
    # Data Science & ML
    "Data Scientist":          ["Python", "Pandas", "Scikit-learn", "TensorFlow", "SQL", "Statistics", "Machine Learning", "Jupyter", "R"],
    "Senior Data Scientist":   ["Python", "TensorFlow", "PyTorch", "MLflow", "Statistics", "Deep Learning", "SQL", "Feature Engineering"],
    "ML Engineer":             ["Python", "TensorFlow", "PyTorch", "Docker", "Kubernetes", "MLflow", "AWS", "FastAPI", "ONNX"],
    "AI Engineer":             ["Python", "LangChain", "OpenAI", "RAG", "Vector DB", "FastAPI", "Docker", "Transformers", "Hugging Face"],
    "Research Scientist":      ["Python", "PyTorch", "Deep Learning", "NLP", "Computer Vision", "Mathematics", "Publications"],
    "Applied Scientist":       ["Python", "Machine Learning", "Statistics", "AWS", "Deep Learning", "NLP", "A/B Testing"],
    "NLP Engineer":            ["Python", "NLP", "Transformers", "Hugging Face", "spaCy", "BERT", "LLM", "FastAPI"],
    "Computer Vision Engineer":["Python", "OpenCV", "PyTorch", "TensorFlow", "Computer Vision", "Deep Learning", "CUDA"],
    "MLOps Engineer":          ["Python", "MLflow", "Kubeflow", "Docker", "Kubernetes", "AWS", "CI/CD", "Terraform"],
    "Deep Learning Engineer":  ["Python", "PyTorch", "TensorFlow", "CUDA", "Deep Learning", "Mathematics", "GPU"],
    "AI Research Lead":        ["Python", "PyTorch", "Deep Learning", "Research", "Leadership", "Publications", "NLP"],
    # Security
    "Security Engineer":       ["Python", "Linux", "OWASP", "AWS", "Penetration Testing", "Security", "Networking", "SIEM"],
    "Security Analyst":        ["SIEM", "SOC", "Incident Response", "Forensics", "Networking", "Linux", "Splunk"],
    "Penetration Tester":      ["Penetration Testing", "Burp Suite", "Linux", "Python", "OWASP", "Networking", "Metasploit"],
    "SOC Analyst":             ["SIEM", "SOC", "Incident Response", "Splunk", "Networking", "Malware Analysis"],
    "Cloud Security Engineer": ["AWS", "Azure", "Security", "IAM", "Terraform", "Compliance", "Zero Trust"],
    "AppSec Engineer":         ["OWASP", "SAST", "DAST", "Python", "Security", "Code Review", "DevSecOps"],
    "Security Architect":      ["Architecture", "Security", "Cloud", "Zero Trust", "IAM", "Compliance", "Risk Assessment"],
    "CISO":                    ["Leadership", "Security Strategy", "Compliance", "Risk Management", "Governance", "Team Management"],
    "Threat Intelligence Analyst":["Threat Intelligence", "OSINT", "SIEM", "Malware Analysis", "Cyber Threat", "Reporting"],
    "Identity & Access Management Engineer": ["IAM", "OAuth", "SAML", "Azure AD", "Okta", "Security", "Python"],
    # QA
    "QA Engineer":             ["Selenium", "Python", "JIRA", "SQL", "Manual Testing", "API Testing", "Postman"],
    "Senior QA Engineer":      ["Selenium", "Cypress", "Python", "CI/CD", "API Testing", "Performance Testing", "JIRA"],
    "SDET":                    ["Python", "Java", "Selenium", "Cypress", "REST", "Docker", "CI/CD", "Git"],
    "Automation Test Engineer":["Selenium", "Cypress", "Python", "Jenkins", "Docker", "REST", "Postman"],
    "Performance Test Engineer":["JMeter", "Gatling", "Load Testing", "Performance Testing", "Python", "Monitoring"],
    "QA Lead":                 ["Test Strategy", "Selenium", "JIRA", "Leadership", "CI/CD", "Agile", "Mentoring"],
    "Test Manager":            ["Test Strategy", "Leadership", "JIRA", "Agile", "Budgeting", "Reporting", "Team Management"],
    "Manual Tester":           ["Manual Testing", "JIRA", "SQL", "Test Cases", "Bug Reporting", "Regression Testing"],
    # Product
    "Product Manager":         ["Product Strategy", "Agile", "JIRA", "User Research", "Data Analysis", "Roadmapping", "A/B Testing"],
    "Senior Product Manager":  ["Product Strategy", "Roadmapping", "Stakeholder Management", "Data Analysis", "A/B Testing", "Leadership"],
    "Group PM":                ["Leadership", "Product Strategy", "Roadmapping", "Business Strategy", "Team Management"],
    "VP of Product":           ["Leadership", "Product Strategy", "Business Strategy", "P&L", "Board Reporting", "Vision"],
    "Technical Product Manager":["APIs", "System Design", "Agile", "SQL", "Technical Architecture", "Roadmapping"],
    "Associate Product Manager":["Product Analysis", "JIRA", "User Research", "SQL", "Agile", "Communication"],
    "Product Owner":           ["Agile", "Scrum", "JIRA", "User Stories", "Backlog Management", "Stakeholder Management"],
    # Design
    "UX Designer":             ["Figma", "User Research", "Wireframing", "Prototyping", "Usability Testing", "Design Systems"],
    "UI Designer":             ["Figma", "Photoshop", "UI Design", "Design Systems", "Typography", "Color Theory"],
    "Product Designer":        ["Figma", "User Research", "Prototyping", "Design Systems", "Interaction Design", "Usability"],
    "UX Researcher":           ["User Research", "Surveys", "Interviews", "Usability Testing", "Data Analysis", "Reporting"],
    "Interaction Designer":    ["Figma", "Prototyping", "Animation", "Interaction Design", "Micro-interactions"],
    "Visual Designer":         ["Photoshop", "Illustrator", "Figma", "Branding", "Typography", "Color Theory"],
    "Design Lead":             ["Figma", "Leadership", "Design Systems", "Mentoring", "User Research", "Stakeholder Management"],
    "Head of Design":          ["Leadership", "Design Strategy", "Team Management", "Branding", "Vision", "Hiring"],
    # Cloud & Networking
    "Cloud Solutions Architect": ["AWS", "Azure", "GCP", "Architecture", "Terraform", "Kubernetes", "Networking", "Security"],
    "Network Engineer":        ["Cisco", "Networking", "Firewalls", "VPN", "TCP/IP", "BGP", "OSPF", "Linux"],
    "Network Security Engineer":["Firewalls", "IDS/IPS", "VPN", "Networking", "Security", "Cisco", "Palo Alto"],
    "Wireless Engineer":       ["Wi-Fi", "Wireless", "RF", "Cisco", "Networking", "Site Survey"],
    "Cloud Consultant":        ["AWS", "Azure", "GCP", "Cloud Migration", "Architecture", "Terraform", "Cost Optimization"],
    "Cloud Migration Specialist":["AWS", "Azure", "Cloud Migration", "Terraform", "Docker", "Networking", "Assessment"],
    # Business
    "Business Analyst":        ["SQL", "Business Analysis", "JIRA", "Requirements", "Power BI", "Excel", "Stakeholder Management"],
    "Management Consultant":   ["Strategy", "Business Analysis", "PowerPoint", "Excel", "Financial Modeling", "Communication"],
    "Strategy Analyst":        ["Strategy", "Financial Modeling", "Excel", "PowerPoint", "Data Analysis", "Market Research"],
    "Operations Manager":      ["Operations", "Leadership", "Process Improvement", "Excel", "Budgeting", "Team Management"],
    "Business Development Manager": ["Sales", "Negotiation", "CRM", "Strategy", "Communication", "Partnership"],
    "Growth Manager":          ["Growth Hacking", "A/B Testing", "SQL", "Analytics", "Marketing", "Product"],
    # Sales & Marketing
    "Digital Marketing Manager":["SEO", "Google Analytics", "Social Media", "Content Marketing", "Paid Ads", "Email Marketing"],
    "SEO Specialist":          ["SEO", "Google Analytics", "Content Strategy", "Technical SEO", "Link Building", "Ahrefs"],
    "Content Marketing Manager":["Content Strategy", "SEO", "Copywriting", "Social Media", "Analytics", "Brand Voice"],
    "Growth Hacker":           ["Growth Hacking", "A/B Testing", "Analytics", "SQL", "Python", "Marketing Automation"],
    "Sales Engineer":          ["Technical Sales", "Demos", "APIs", "Cloud", "CRM", "Communication", "Python"],
    "Account Executive":       ["Sales", "CRM", "Negotiation", "Pipeline Management", "Communication", "SaaS"],
    "Marketing Analyst":       ["Google Analytics", "SQL", "Excel", "Tableau", "A/B Testing", "Python"],
    "Brand Manager":           ["Branding", "Marketing Strategy", "Creative Direction", "Market Research", "Communication"],
    # HR
    "HR Manager":              ["HR Management", "Compliance", "Payroll", "Employee Relations", "HRIS", "Leadership"],
    "Technical Recruiter":     ["Recruiting", "LinkedIn", "ATS", "Boolean Search", "Interviewing", "Tech Stack Knowledge"],
    "Talent Acquisition Lead": ["Recruiting", "Leadership", "Employer Branding", "ATS", "Strategy", "Team Management"],
    "People Operations Manager":["People Ops", "HRIS", "Culture", "Benefits", "Compliance", "Analytics"],
    "HR Business Partner":     ["HR Strategy", "Employee Relations", "Performance Management", "Coaching", "Analytics"],
    "Compensation Analyst":    ["Compensation", "Excel", "Market Research", "HRIS", "Analytics", "Benchmarking"],
    "L&D Specialist":          ["Training", "Learning Design", "LMS", "Communication", "Facilitation", "E-learning"],
    # Finance
    "Financial Analyst":       ["Financial Modeling", "Excel", "SQL", "Power BI", "Financial Analysis", "Budgeting"],
    "Quantitative Analyst":    ["Python", "R", "Statistics", "Machine Learning", "Financial Modeling", "Mathematics", "C++"],
    "Risk Analyst":            ["Risk Analysis", "Excel", "SQL", "Financial Modeling", "Compliance", "Statistics"],
    "FinTech Developer":       ["Python", "Node.js", "REST", "PostgreSQL", "Payment Systems", "Docker", "Security"],
    "Blockchain Developer":    ["Solidity", "Ethereum", "Web3.js", "Smart Contracts", "Blockchain", "JavaScript", "DeFi"],
    "Payment Systems Engineer":["Payment Gateway", "REST", "Python", "PostgreSQL", "Security", "PCI-DSS", "Docker"],
    "Treasury Analyst":        ["Treasury", "Excel", "Financial Modeling", "Cash Management", "Banking", "SAP"],
    "Credit Risk Modeler":     ["Python", "R", "Statistics", "Machine Learning", "Credit Risk", "SQL", "SAS"],
    # Healthcare
    "Health Informatics Specialist": ["HL7", "FHIR", "SQL", "Healthcare IT", "Data Analysis", "EHR"],
    "Clinical Data Analyst":   ["SQL", "R", "Python", "Clinical Data", "Statistics", "SAS", "Reporting"],
    "EHR Implementation Specialist": ["EHR", "Epic", "Cerner", "Healthcare IT", "SQL", "Project Management"],
    "Bioinformatics Engineer": ["Python", "R", "Bioinformatics", "Genomics", "Statistics", "Linux", "Databases"],
    "Healthcare Software Developer": ["Python", "Java", "HL7", "FHIR", "REST", "PostgreSQL", "Docker"],
    "Medical Device Engineer": ["C++", "Embedded", "Medical Devices", "Regulatory", "Testing", "Python"],
    "Telemedicine Developer":  ["React", "Node.js", "WebRTC", "REST", "PostgreSQL", "Docker", "HIPAA"],
    # E-Commerce
    "E-Commerce Developer":   ["React", "Node.js", "PostgreSQL", "REST", "Stripe", "Docker", "Redis"],
    "Shopify Developer":       ["Shopify", "Liquid", "JavaScript", "REST", "GraphQL", "CSS", "E-commerce"],
    "Supply Chain Analyst":    ["SQL", "Excel", "SAP", "Supply Chain", "Data Analysis", "Power BI"],
    "Inventory Analyst":       ["SQL", "Excel", "Inventory Management", "SAP", "Data Analysis", "Forecasting"],
    "Marketplace Engineer":    ["Python", "Node.js", "PostgreSQL", "Elasticsearch", "Docker", "Microservices"],
    "Recommendation Engine Engineer": ["Python", "Machine Learning", "Collaborative Filtering", "TensorFlow", "Redis", "SQL"],
    # EdTech
    "EdTech Developer":        ["React", "Node.js", "Python", "PostgreSQL", "REST", "Docker", "LMS"],
    "Instructional Designer":  ["Instructional Design", "LMS", "E-Learning", "SCORM", "Articulate", "Communication"],
    "LMS Administrator":       ["LMS", "Moodle", "Canvas", "Administration", "SQL", "Reporting"],
    "Curriculum Developer":    ["Curriculum Design", "Education", "Content Creation", "LMS", "Assessment"],
    "Educational Data Analyst":["SQL", "Python", "Education Analytics", "Tableau", "Statistics", "Reporting"],
    # Gaming
    "Game Developer":          ["Unity", "C#", "Game Design", "3D", "Physics", "Git", "Optimization"],
    "Unity Developer":         ["Unity", "C#", "3D", "Game Design", "Shader Programming", "Git"],
    "Unreal Engine Developer": ["Unreal Engine", "C++", "Blueprints", "3D", "Game Design"],
    "Game Designer":           ["Game Design", "Level Design", "Balancing", "Prototyping", "Unity"],
    "Graphics Programmer":     ["OpenGL", "Vulkan", "C++", "Shader Programming", "3D", "Math"],
    "Technical Artist":        ["Unity", "Shader Programming", "3D Art", "Technical Art", "Pipeline"],
    "VR/AR Developer":         ["Unity", "VR", "AR", "C#", "3D", "Spatial Computing", "Oculus"],
    # Telecom
    "Telecom Engineer":        ["Telecom", "Networking", "5G", "RF", "Protocol", "Linux"],
    "RF Engineer":             ["RF Design", "Antenna", "5G", "LTE", "MATLAB", "Simulation"],
    "5G Network Engineer":     ["5G", "NR", "Networking", "Linux", "Protocol", "Ericsson"],
    "OSS/BSS Developer":       ["Java", "OSS", "BSS", "Telecom", "REST", "SQL", "Microservices"],
    "VoIP Engineer":           ["VoIP", "SIP", "Asterisk", "Networking", "Linux", "Troubleshooting"],
    # Media
    "Content Writer":          ["Copywriting", "SEO", "Content Strategy", "Research", "Editing", "WordPress"],
    "Technical Writer":        ["Technical Writing", "Documentation", "Markdown", "API Docs", "Git", "Developer Docs"],
    "Video Editor":            ["Premiere Pro", "After Effects", "DaVinci Resolve", "Motion Graphics", "Color Grading"],
    "Streaming Platform Engineer": ["Python", "FFmpeg", "CDN", "AWS", "Docker", "Microservices", "Redis"],
    "CMS Developer":           ["WordPress", "Drupal", "PHP", "JavaScript", "MySQL", "REST", "Docker"],
    # Legal Tech
    "Legal Tech Developer":    ["Python", "NLP", "REST", "PostgreSQL", "Docker", "Contract Analysis"],
    "Contract Analyst":        ["Contract Law", "NLP", "Data Analysis", "Excel", "Legal Research"],
    "Compliance Engineer":     ["Compliance", "Python", "Automation", "SOC 2", "GDPR", "Risk Assessment"],
    "RegTech Developer":       ["Python", "REST", "PostgreSQL", "Compliance", "Automation", "Docker"],
    # Construction & PropTech
    "BIM Engineer":            ["BIM", "Revit", "AutoCAD", "3D Modeling", "Construction", "Navisworks"],
    "PropTech Developer":      ["React", "Node.js", "PostgreSQL", "REST", "Maps API", "Docker"],
    "GIS Analyst":             ["GIS", "ArcGIS", "QGIS", "Python", "Spatial Data", "SQL"],
    "Smart Building Engineer": ["IoT", "BMS", "Python", "Networking", "HVAC", "Automation"],
    # Energy & CleanTech
    "Energy Data Analyst":     ["Python", "SQL", "Energy Analytics", "Power BI", "Statistics", "Excel"],
    "IoT Engineer":            ["IoT", "Python", "MQTT", "Embedded", "AWS IoT", "Networking", "C"],
    "SCADA Engineer":          ["SCADA", "PLC", "Industrial Automation", "Networking", "Python"],
    "Renewable Energy Developer": ["Python", "Data Analysis", "Renewable Energy", "Simulation", "Excel"],
    "Smart Grid Engineer":     ["Smart Grid", "Power Systems", "SCADA", "Python", "Data Analysis"],
    # Logistics
    "Supply Chain Developer":  ["Python", "SQL", "REST", "Logistics", "Docker", "Optimization"],
    "Logistics Analyst":       ["SQL", "Excel", "Logistics", "Data Analysis", "Power BI", "SAP"],
    "Route Optimization Engineer": ["Python", "Algorithms", "Optimization", "GIS", "OR", "Machine Learning"],
    "Warehouse Automation Engineer": ["PLC", "Automation", "Python", "IoT", "Robotics", "Networking"],
    # Government
    "GovTech Developer":       ["Python", "React", "PostgreSQL", "REST", "Docker", "Security", "Accessibility"],
    "Public Sector Analyst":   ["SQL", "Excel", "Data Analysis", "Power BI", "Reporting", "Policy"],
    "Digital Transformation Specialist": ["Project Management", "Change Management", "Cloud", "Agile", "Stakeholder Management"],
    "e-Governance Architect":  ["Architecture", "Cloud", "Security", "REST", "PostgreSQL", "Python"],
    # Automotive
    "ADAS Engineer":           ["C++", "Python", "Computer Vision", "Sensor Fusion", "ADAS", "ROS"],
    "Autonomous Vehicle Engineer": ["Python", "C++", "ROS", "Computer Vision", "Deep Learning", "Sensor Fusion", "LiDAR"],
    "Connected Car Developer": ["IoT", "MQTT", "Python", "REST", "AWS", "Embedded", "Security"],
    "Telematics Engineer":     ["Telematics", "IoT", "Python", "Embedded", "Networking", "GPS"],
    "EV Battery Management Developer": ["Python", "Embedded", "BMS", "C++", "Simulation", "MATLAB"],
}



# location weighted india gets mroe weighted
LOCATIONS: list[tuple[str, str, int]] = [
    # (city, country, weight)
    ("Bengaluru", "India", 12),
    ("Mumbai", "India", 8),
    ("Delhi", "India", 6),
    ("Hyderabad", "India", 6),
    ("Chennai", "India", 4),
    ("Pune", "India", 4),
    ("Noida", "India", 3),
    ("Gurugram", "India", 3),
    ("Kolkata", "India", 2),
    ("Ahmedabad", "India", 2),
    ("New York", "United States", 5),
    ("San Francisco", "United States", 5),
    ("Seattle", "United States", 3),
    ("Austin", "United States", 3),
    ("Chicago", "United States", 2),
    ("Boston", "United States", 2),
    ("London", "United Kingdom", 5),
    ("Manchester", "United Kingdom", 2),
    ("Toronto", "Canada", 3),
    ("Vancouver", "Canada", 2),
    ("Berlin", "Germany", 2),
    ("Munich", "Germany", 1),
    ("Sydney", "Australia", 2),
    ("Melbourne", "Australia", 1),
    ("Singapore", "Singapore", 3),
    ("Dubai", "UAE", 2),
    ("Amsterdam", "Netherlands", 1),
    ("Paris", "France", 1),
    ("Tokyo", "Japan", 1),
    ("Remote", "Remote", 5),
]
# Pre-compute weighted lists for random.choices()
_CITIES = [loc[0] for loc in LOCATIONS]
_COUNTRIES = [loc[1] for loc in LOCATIONS]
_WEIGHTS = [loc[2] for loc in LOCATIONS]

# Education levels
EDUCATION_LEVELS = ["Bachelors", "Masters", "PhD", None]
EDUCATION_WEIGHTS = [50, 35, 5, 10]  # 50% Bachelors, 35% Masters, etc.

EXPERIENCE_BANDS = [
    (0, 2, 25),     # 25% Junior (0-2 years)
    (3, 5, 30),     # 30% Mid (3-5 years)
    (6, 10, 25),    # 25% Senior (6-10 years)
    (11, 15, 12),   # 12% Staff/Lead (11-15 years)
    (16, 25, 8),    # 8% Director/VP (16-25 years)
]

_EXP_RANGES = [(lo, hi) for lo, hi, _ in EXPERIENCE_BANDS]
_EXP_WEIGHTS = [w for _, _, w in EXPERIENCE_BANDS]

# companies anmes faker eneerated orginal type
COMPANIES = [
    "Google", "Microsoft", "Amazon", "Meta", "Apple", "Netflix",
    "Uber", "Airbnb", "Stripe", "Shopify", "Salesforce", "Adobe",
    "Oracle", "IBM", "SAP", "Infosys", "TCS", "Wipro", "HCL",
    "Cognizant", "Tech Mahindra", "Accenture", "Deloitte", "McKinsey",
    "Goldman Sachs", "JP Morgan", "Morgan Stanley", "Citadel",
    "Flipkart", "Swiggy", "Zomato", "PhonePe", "Paytm", "Ola",
    "Razorpay", "Zerodha", "CRED", "Meesho", "Dream11",
    "Atlassian", "Databricks", "Snowflake", "Confluent", "HashiCorp",
    "Palantir", "Twilio", "Cloudflare", "Datadog", "GitLab",
    "SpaceX", "Tesla", "Rivian", "Cruise", "Waymo",
]

# text generator for resumes
def generate_resume_text(
    name:str,
    title: str,
    industry: str,
    skills: list[str],
    years: int,
    company: str,
    education: str | None,
    city: str,
    country: str,
) -> str:
    """Build realistic fake resume text — LLM reads this field for scoring."""
    # Generate some realistic work experience bullets
    bullets = [
        f"Led development of {fake.bs()} using {random.choice(skills)} and {random.choice(skills)}",
        f"Designed and implemented {fake.catch_phrase().lower()} system handling {random.randint(100, 10000)} daily requests",
        f"Reduced {random.choice(['latency', 'costs', 'deployment time', 'error rates'])} by {random.randint(15, 70)}% through {random.choice(skills)} optimization",
        f"Collaborated with {random.randint(3, 15)}-person cross-functional team on {fake.bs()}",
        f"Mentored {random.randint(2, 8)} junior engineers on {random.choice(skills)} best practices",
        f"Built CI/CD pipeline reducing release cycle from {random.randint(2, 4)} weeks to {random.randint(1, 3)} days",
        f"Architected {random.choice(['microservices', 'event-driven', 'serverless', 'distributed'])} solution serving {random.randint(1, 50)}M users",
        f"Implemented {random.choice(skills)} integration improving {random.choice(['throughput', 'reliability', 'scalability'])} by {random.randint(20, 90)}%",
    ]

    # pick 3-5 random bullets
    selected_bullets= random.sample(bullets,min(random.randint(3,5),
    len(bullets)))

    # Generate 1-2 previous companies
    prev_companies = random.sample(COMPANIES, min(2, len(COMPANIES)))

    edu_section=""

    if education:
        universities = [
    "IIT Bombay", "IIT Delhi", "NIT Trichy", "BITS Pilani",
    "MIT", "Stanford University", "UC Berkeley",
    "University of London", "University of Toronto",
    "National University of Singapore",
    "VIT Vellore", "SRM University", "DTU Delhi",
    "Georgia Tech", "Carnegie Mellon", "ETH Zurich",

    

    "IIT Madras", "IIT Kanpur", "IIT Kharagpur", "IIT Roorkee",
    "NIT Surathkal", "NIT Warangal", "IIIT Hyderabad", "IIIT Bangalore",
    "Jadavpur University", "Anna University", "Delhi University",

    "Harvard University", "Princeton University", "Yale University",
    "Columbia University", "University of Chicago",
    "University of California Los Angeles", "UC San Diego",
    "University of Washington", "New York University",

    "Oxford University", "Cambridge University",
    "Imperial College London", "University College London",
    "University of Edinburgh",

    "Tsinghua University", "Peking University",
    "University of Tokyo", "KAIST",
    "Seoul National University", "Hong Kong University",

    "University of Melbourne", "Australian National University",
    "Technical University of Munich", "RWTH Aachen",
        ]

        edu_section = f"""
EDUCATION
{education} in {random.choice(['Computer Science', 'Information Technology', 'Software Engineering', 'Data Science', 'Electronics', 'Mathematics', 'Business Administration'])}
{random.choice(universities)}, {random.randint(2005, 2023)}
"""

    text = f"""{name}
    {title} | {city}, {country}
    {fake.email()} | +{fake.msisdn()[:12]}
    PROFESSIONAL SUMMARY
    {title} with {years}+ years of experience in {industry}. 
    Proficient in {', '.join(skills[:5])}. 
    {fake.paragraph(nb_sentences=3)}
    SKILLS
    {', '.join(skills)}
    EXPERIENCE
    {title} at {company}
    {random.randint(max(2015, 2024-years), 2024)} - Present
    {chr(10).join('• ' + b for b in selected_bullets[:3])}
    {random.choice(['Senior', 'Lead', '']) + ' ' + title.split()[-1]} at {prev_companies[0]}
    {random.randint(2012, 2020)} - {random.randint(2020, 2023)}
    {chr(10).join('• ' + b for b in selected_bullets[3:])}
    {edu_section}
    CERTIFICATIONS
    • {random.choice(['AWS Solutions Architect', 'Google Cloud Professional', 'Azure Administrator', 'Kubernetes Administrator', 'PMP', 'Scrum Master', 'CISSP', 'CISA'])}
    • {random.choice(['Python Professional', 'Java SE Certified', 'Terraform Associate', 'Docker Certified', 'React Developer', 'MongoDB Developer'])}
    """
    return text.strip()


# generating a single fake candidate
def generate_candidate(index: int) -> dict:
    """Generate a single fake candidate with all required fields."""
    # Pick random industry and role
    industry = random.choice(list(INDUSTRY_ROLES.keys()))
    role = random.choice(INDUSTRY_ROLES[industry])
    # Get role-specific skills (4-8 from the role's skill pool)
    role_skill_pool = ROLE_SKILLS.get(role, ["Python", "SQL", "Git", "Docker", "REST"])
    num_skills = random.randint(4, min(8, len(role_skill_pool)))
    skills = random.sample(role_skill_pool, num_skills)
    # Experience (weighted distribution)
    exp_range = random.choices(_EXP_RANGES, weights=_EXP_WEIGHTS, k=1)[0]
    years = random.randint(exp_range[0], exp_range[1])
    # Education (weighted distribution)
    education = random.choices(EDUCATION_LEVELS, weights=EDUCATION_WEIGHTS, k=1)[0]
    # Location (weighted distribution)
    loc_idx = random.choices(range(len(LOCATIONS)), weights=_WEIGHTS, k=1)[0]
    city, country = _CITIES[loc_idx], _COUNTRIES[loc_idx]
    # Company
    company = random.choice(COMPANIES)
    # Name and contact
    name = fake.name()
    email = fake.unique.email()
    phone = f"+{fake.msisdn()[:12]}"
    # Generate resume text
    resume_text = generate_resume_text(
        name=name, title=role, industry=industry,
        skills=skills, years=years, company=company,
        education=education, city=city, country=country,
    )
    # Build external_id from index (deterministic, idempotent)
    external_id = f"mock-{hashlib.md5(f'mock-candidate-{index}'.encode()).hexdigest()[:16]}"
    return {
        "id": uuid.uuid4(),
        "external_id": external_id,
        "full_name": name[:256],
        "email": email[:320],
        "phone": phone[:32],
        "location_city": city,
        "location_country": country,
        "years_of_experience": years,
        "current_title": role[:256],
        "current_company": company[:256],
        "education_level": education,
        "skills": skills,
        "resume_text": resume_text,
        "resume_blob_url": None,
        "vector_id": None,
        "is_active": True,
    }


# Batch inserting in supabase
BATCH_SIZE=50

async def insert_candidates(candidates: list[dict]) -> int:
    # Batch inserting into supabase
    engine=create_async_engine(settings.DATABASE_URL,echo=False)

    insert_sql=text("""
    INSERT INTO candidates (
            id, external_id, full_name, email, phone,
            location_city, location_country, years_of_experience,
            current_title, current_company, education_level,
            skills, resume_text, resume_blob_url, vector_id, is_active) VALUES (
            :id, :external_id, :full_name, :email, :phone,
            :location_city, :location_country, :years_of_experience,
            :current_title, :current_company, :education_level,
            CAST(:skills AS jsonb), :resume_text, :resume_blob_url, :vector_id, :is_active
            )
            ON CONFLICT (external_id) DO NOTHING
            """)

    inserted=0
    failed_batches=0
    for i in range(0,len(candidates), BATCH_SIZE):
        batch = candidates[i:i + BATCH_SIZE]
        try:
            async with engine.begin() as conn:
                for candidate in batch:
                    params={**candidate,"skills":json.dumps(candidate["skills"])}
                    await conn.execute(insert_sql,params)
                inserted+=len(batch)
        except Exception as e:
            failed_batches += 1
            if failed_batches <= 3:
                logger.warning("batch_failed", batch_start=i, error=str(e)[:200])
        if (i + BATCH_SIZE) % 500 == 0:
            logger.info("insert_progress", done=min(i + BATCH_SIZE, len(candidates)),
                        total=len(candidates))
    if failed_batches > 0:
        logger.info("insert_summary", inserted=inserted, failed_batches=failed_batches)
    await engine.dispose()
    return inserted


async def main() -> None:
    logger.info("mock_seed_started", target=TARGET_COUNT)
    # Step 1: Check how many we already have
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM candidates"))
        existing = result.scalar()
    await engine.dispose()
    needed = max(0, 10000 - existing)
    if needed == 0:
        logger.info("already_at_target", existing=existing)
        print(f"\n  Already have {existing} candidates. Target is 10,000. Nothing to do!")
        return
    actual_count = min(needed, TARGET_COUNT)
    logger.info("generating", existing=existing, needed=needed, generating=actual_count)
    # Step 2: Generate candidates
    candidates = []
    for i in tqdm(range(actual_count), desc="Generating candidates", unit="candidate"):
        candidates.append(generate_candidate(i))
    # Step 3: Print distribution stats
    industries = {}
    for c in candidates:
        # figure out industry from role
        for ind, roles in INDUSTRY_ROLES.items():
            if c["current_title"] in roles:
                industries[ind] = industries.get(ind, 0) + 1
                break
    print(f"\n  Generated {len(candidates)} candidates across {len(industries)} industries")
    print(f"  Top 10 industries:")
    for ind, count in sorted(industries.items(), key=lambda x: -x[1])[:10]:
        print(f"    {ind}: {count}")
    # Step 4: Insert into Supabase
    logger.info("inserting", count=len(candidates))
    inserted = await insert_candidates(candidates)
    # Step 5: Final count
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM candidates"))
        total = result.scalar()
    await engine.dispose()
    print("\n" + "=" * 60)
    print("  SEED MOCK CANDIDATES — SUMMARY")
    print("=" * 60)
    print(f"  Previously in DB:  {existing}")
    print(f"  Generated:         {len(candidates)}")
    print(f"  Inserted to DB:    {inserted}")
    print(f"  Total in DB now:   {total}")
    print("=" * 60)
if __name__ == "__main__":
    asyncio.run(main())