"""The gap library: common reasons a local business is missing from AI answers.

Each gap has plain-English text for the report. In an audit's findings.toml you
pick the gaps you actually confirmed and add one specific detail line for each.
"""
from __future__ import annotations

GAPS = {
    "gbp": {
        "title": "Google Business Profile is incomplete",
        "why": "Google's AI and Gemini lean on your Google profile: categories, services, hours, photos and Q&A.",
        "quick_win": "Fill in every Google Business Profile field: all services with a short description, hours, and 10+ recent photos.",
        "plan": "A fully built Google Business Profile with every service listed, weekly posts and answered Q&A.",
    },
    "reviews": {
        "title": "Fewer reviews than the businesses AI picks",
        "why": "AI answers often name review counts and star ratings as the reason they chose someone.",
        "quick_win": "Ask your last 20 happy clients for a Google review with a direct link (text or email). Reply to every review.",
        "plan": "A steady, simple review request routine after each visit, so your count keeps climbing.",
    },
    "faq_pages": {
        "title": "No FAQ answers on your website",
        "why": "AI tools quote pages that answer questions directly, such as cost, recovery time or who it's right for.",
        "quick_win": "Add an FAQ section answering the 5 questions clients ask most, in plain words, with prices or ranges where you can.",
        "plan": "FAQ content on your site that matches the exact questions people ask AI tools.",
    },
    "service_pages": {
        "title": "Services are not on their own pages",
        "why": "When each treatment has its own page, AI can match you to a question like 'best place for lip filler in your town'.",
        "quick_win": "Write one page for your single most profitable service: what it is, who it's for, price range, and your town's name.",
        "plan": "One clear page per main service, each naming your town and nearby areas.",
    },
    "directories": {
        "title": "Missing from the sites AI cites",
        "why": "AI answers pull from directories and review sites. If you're not listed there, you're hard to recommend.",
        "quick_win": "Claim or update your listing on the 2 directories AI cited most in this audit.",
        "plan": "Complete, matching listings on every directory the AI tools cite for your industry.",
    },
    "nap": {
        "title": "Name, address or phone don't match across sites",
        "why": "When your details differ from site to site, AI is less sure the listings are the same business.",
        "quick_win": "Make your name, address and phone exactly the same on your website, Google, Yelp and Facebook.",
        "plan": "Clean, matching business details everywhere you're listed.",
    },
    "schema": {
        "title": "Website has no business markup (schema)",
        "why": "Schema is hidden code that tells search engines and AI your business type, services, hours and location.",
        "quick_win": "Ask your web person to add LocalBusiness (or MedicalBusiness) schema to your homepage. It takes under an hour.",
        "plan": "Proper business and service markup on your website.",
    },
    "local_mentions": {
        "title": "Few mentions in local news, blogs or 'best of' lists",
        "why": "AI trusts businesses other local sites talk about.",
        "quick_win": "Enter one local 'best of' award and list yourself with your chamber of commerce.",
        "plan": "A handful of real local mentions: chamber, local blogs, community events.",
    },
}
