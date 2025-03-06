#!/usr/bin/env python3
import requests
import feedparser
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import urllib.parse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
from rich.console import Console

class DailyBiotechTrackerHTML:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # RSS feeds for news sources
        self.news_sources = {
            "Biotech Industry": [
                "https://feeds.feedburner.com/FierceBiotech",
                "https://www.pharmalive.com/category/biotech/feed/",
                "https://www.biospace.com/rss/news/",
                "https://www.genengnews.com/feed/",
                "https://www.bioworld.com/feeds/rss/bioworld-today.xml",
                "https://www.labiotech.eu/feed/",
                "https://endpts.com/feed/"
            ],
            "Microbiome News": [
                "https://microbiomedigest.com/feed/",
                "https://www.the-scientist.com/tag/microbiome/feed",
                "https://www.cell.com/trends/microbiology/inpress.rss",
                "https://feeds.feedburner.com/MicrobiomePost"
            ],
            "General Science News": [
                "https://www.sciencedaily.com/rss/top/science.xml",
                "https://www.nature.com/nature/articles.rss",
                "https://science.sciencemag.org/rss/current.xml",
                "https://www.newscientist.com/feed/home/?cmpid=RSS",
                "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
            ]
        }
        self.ncbi_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        self.today = datetime.now()
        self.date_str = self.today.strftime('%Y-%m-%d')
        # Keywords with weights for relevance scoring (as in your original script)
        self.keywords = {
            "Biotech & Microbiome Focus": {
                "microbiome business": 10,
                "microbiome company": 10,
                "microbiome startup": 10,
                "microbiome investment": 9,
                "microbiome clinical trial": 10,
                "microbiome stock": 9,
                "microbiome therapeutics": 9,
                "antimicrobial resistance": 8,
                "live biotherapeutic": 8,
                "fecal microbiota transplant": 7,
                "gut-brain axis": 7,
                "skin microbiome product": 9,
                "microbiome diagnostic": 8
            },
            "Synthetic & Molecular Biology": {
                "synthetic biology": 10,
                "molecular biology": 9,
                "microbiology technique": 8,
                "bacteria engineering": 10,
                "plasmid design": 9,
                "gene expression": 8,
                "CRISPR": 9,
                "bacterial defense system": 9,
                "restriction enzyme": 8,
                "bacteria measurement": 7,
                "microscopy bacteria": 7,
                "single-cell sequencing": 8,
                "gene editing bacteria": 9,
                "biosensor bacteria": 8,
                "metabolic engineering": 8
            },
            "Bacteriophage Research": {
                "bacteriophage": 10,
                "phage therapy": 10,
                "phage engineering": 10,
                "phage display": 8,
                "phage cocktail": 9,
                "phage resistance": 9,
                "phage biology": 8,
                "phage genome": 8,
                "temperate phage": 7,
                "virulent phage": 7,
                "bacteriophage isolation": 8,
                "phage-host interaction": 9
            },
            "Skin Microbiome & Disease": {
                "skin microbiome": 10,
                "skin bacteria": 9,
                "Cutibacterium acnes": 10,
                "Propionibacterium acnes": 10,
                "skin microbiome atopic dermatitis": 9,
                "skin microbiome psoriasis": 9,
                "skin microbiome acne": 10,
                "skin microbiome eczema": 9,
                "skin microbiome rosacea": 9,
                "skin microbiome wound": 8,
                "skin microbiome aging": 8,
                "skin microbiome cancer": 8,
                "skin microbiome cosmetic": 8
            }
        }
        self.journal_scores = {
            'Nature': 10,
            'Science': 10,
            'Cell': 10,
            'Nature Biotechnology': 10,
            'Nature Microbiology': 10,
            'Nature Medicine': 9,
            'Nature Communications': 8,
            'Science Translational Medicine': 9,
            'Proceedings of the National Academy of Sciences': 8,
            'Cell Host & Microbe': 9,
            'Microbiome': 9,
            'ISME Journal': 8,
            'Molecular Systems Biology': 8,
            'Trends in Biotechnology': 8,
            'Trends in Microbiology': 8,
            'PLoS Biology': 7,
            'mBio': 7,
            'Nucleic Acids Research': 7,
            'The Journal of Biological Chemistry': 6,
            'Applied and Environmental Microbiology': 6
        }
        self.output_dir = Path('.')
        self.output_dir.mkdir(exist_ok=True)
        self.console = Console()

    def get_news_from_rss(self, feed_url, days_back=2, max_items=5):
        try:
            feed = feedparser.parse(feed_url)
            recent_entries = []
            for entry in feed.entries[:15]:
                if hasattr(entry, 'published_parsed'):
                    pub_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed'):
                    pub_date = datetime(*entry.updated_parsed[:6])
                else:
                    pub_date = datetime.now() - timedelta(days=1)
                if (datetime.now() - pub_date).days <= days_back:
                    recent_entries.append({
                        'title': entry.title,
                        'link': entry.link,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'summary': self.clean_html(entry.get('summary', '')),
                        'source': feed.feed.get('title', 'Unknown Source')
                    })
            recent_entries.sort(key=lambda x: x['date'], reverse=True)
            return recent_entries[:max_items]
        except Exception as e:
            print(f"Error fetching RSS feed {feed_url}: {e}")
            return []

    def clean_html(self, text):
        if not text:
            return ""
        soup = BeautifulSoup(text, 'html.parser')
        text = soup.get_text()
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 300:
            text = text[:297] + '...'
        return text

    def get_all_news(self, category, days_back=2):
        all_news = []
        self.console.print(f"[bold blue]Fetching {category} news...[/bold blue]")
        for feed_url in self.news_sources.get(category, []):
            try:
                news_items = self.get_news_from_rss(feed_url, days_back)
                all_news.extend(news_items)
            except Exception as e:
                self.console.print(f"[red]Error processing {feed_url}: {e}[/red]")
        all_news.sort(key=lambda x: x['date'], reverse=True)
        return all_news

    def search_pubmed(self, query, days_back=7, max_results=8):
        papers = []
        try:
            end_date = self.today
            start_date = end_date - timedelta(days=days_back)
            date_range = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
            final_query = f'({query}) AND {date_range}'
            self.console.print(f"[bold green]Searching PubMed for: {query}...[/bold green]")
            encoded_query = urllib.parse.quote(final_query)
            search_url = f"{self.ncbi_base}esearch.fcgi?db=pubmed&term={encoded_query}&retmax={max_results}&retmode=xml"
            response = requests.get(search_url)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            id_list = root.findall('.//Id')
            if id_list:
                id_string = ','.join(id.text for id in id_list)
                fetch_url = f"{self.ncbi_base}efetch.fcgi?db=pubmed&id={id_string}&retmode=xml"
                response = requests.get(fetch_url)
                response.raise_for_status()
                for article in ET.fromstring(response.content).findall('.//PubmedArticle'):
                    try:
                        paper = self._parse_pubmed_article(article)
                        if paper:
                            paper['source'] = 'PubMed'
                            papers.append(paper)
                    except Exception as e:
                        self.console.print(f"[red]Error processing PubMed article: {e}[/red]")
                        continue
        except Exception as e:
            self.console.print(f"[red]Error in PubMed search: {e}[/red]")
        return papers

    def search_biorxiv(self, keywords, days_back=7):
        papers = []
        try:
            collections = ['microbiology', 'synthetic-biology', 'systems-biology', 'molecular-biology']
            for collection in collections:
                try:
                    url = f"https://api.biorxiv.org/details/biorxiv/{collection}/0"
                    response = requests.get(url)
                    response.raise_for_status()
                    data = response.json()
                    for paper in data.get('collection', []):
                        try:
                            paper_date = datetime.strptime(paper['date'], '%Y-%m-%d')
                            if (self.today - paper_date).days <= days_back:
                                title = paper.get('title', '').lower()
                                abstract = paper.get('abstract', '').lower() 
                                if any(kw.lower() in title or kw.lower() in abstract for kw in keywords):
                                    papers.append({
                                        'title': paper['title'],
                                        'authors': paper['authors'],
                                        'abstract': paper.get('abstract', 'No abstract available'),
                                        'date': paper['date'],
                                        'source': 'bioRxiv',
                                        'url': f"https://doi.org/{paper['doi']}"
                                    })
                        except Exception as e:
                            continue
                except Exception as e:
                    self.console.print(f"[red]Error accessing bioRxiv {collection}: {e}[/red]")
                    continue
        except Exception as e:
            self.console.print(f"[red]Error in bioRxiv search: {e}[/red]")
        return papers

    def calculate_relevance_score(self, paper, category):
        score = 0
        text_to_check = f"{paper['title']} {paper.get('abstract', '')}".lower()
        category_keywords = self.keywords.get(category, {})
        for keyword, weight in category_keywords.items():
            if keyword.lower() in text_to_check:
                score += weight
                if keyword.lower() in paper['title'].lower():
                    score += 3
        journal = paper.get('journal', '').strip()
        score += self.journal_scores.get(journal, 0)
        try:
            pub_date = datetime.strptime(paper['date'], '%Y-%m-%d')
            days_old = (self.today - pub_date).days
            if days_old <= 1:
                score += 5
            elif days_old <= 3:
                score += 3
        except:
            pass
        return score

    def _parse_pubmed_article(self, article):
        article_data = article.find('.//Article')
        if article_data is None:
            return None
        title_elem = article_data.find('.//ArticleTitle')
        journal_elem = article_data.find('.//Journal/Title')
        abstract_elems = article_data.findall('.//Abstract/AbstractText')
        authors = []
        for author in article_data.findall('.//Author'):
            lastname = author.find('LastName')
            firstname = author.find('ForeName')
            if lastname is not None and firstname is not None:
                authors.append(f"{lastname.text} {firstname.text}")
        pub_date = article_data.find('.//PubDate')
        date_str = self._parse_pub_date(pub_date)
        id_list = article.findall('.//ArticleId')
        doi = None
        for id_elem in id_list:
            if id_elem.get('IdType') == 'doi':
                doi = id_elem.text
                break
        pmid = None
        for id_elem in id_list:
            if id_elem.get('IdType') == 'pubmed':
                pmid = id_elem.text
                break
        abstract_text = ""
        for abstract_elem in abstract_elems:
            text = abstract_elem.text or ""
            label = abstract_elem.get('Label')
            if label:
                abstract_text += f"{label}: {text} "
            else:
                abstract_text += f"{text} "
        if not abstract_text:
            abstract_text = "No abstract available"
        if doi:
            url = f"https://doi.org/{doi}"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            url = None
        return {
            'title': title_elem.text if title_elem is not None else "No title available",
            'authors': ', '.join(authors[:3]) + (' et al.' if len(authors) > 3 else ''),
            'journal': journal_elem.text if journal_elem is not None else "Journal not specified",
            'date': date_str,
            'abstract': abstract_text.strip(),
            'url': url
        }

    def _parse_pub_date(self, pub_date):
        if pub_date is not None:
            year = pub_date.find('Year')
            month = pub_date.find('Month')
            day = pub_date.find('Day')
            year_str = year.text if year is not None else '2023'
            if month is not None:
                month_text = month.text
                try:
                    int(month_text)
                    month_str = month_text.zfill(2)
                except ValueError:
                    try:
                        month_dt = datetime.strptime(month_text[:3], '%b')
                        month_str = str(month_dt.month).zfill(2)
                    except:
                        month_str = '01'
            else:
                month_str = '01'
            day_str = day.text.zfill(2) if day is not None else '01'
            return f"{year_str}-{month_str}-{day_str}"
        return "Date not available"

    def search_all_pubmed_categories(self, days_back=7):
        results = {}
        for category, keywords in self.keywords.items():
            query_terms = []
            for keyword in keywords.keys():
                query_terms.append(f'"{keyword}"[All Fields]')
            query = ' OR '.join(query_terms)
            papers = self.search_pubmed(query, days_back=days_back)
            bioRxiv_papers = self.search_biorxiv(list(keywords.keys()), days_back=days_back)
            all_papers = papers + bioRxiv_papers
            for paper in all_papers:
                paper['relevance_score'] = self.calculate_relevance_score(paper, category)
            all_papers.sort(key=lambda x: x['relevance_score'], reverse=True)
            results[category] = all_papers
        return results

    def generate_html_report(self, news_data, paper_data):
        html_lines = []
        html_lines.append("<html>")
        html_lines.append("<head>")
        html_lines.append("<meta charset='utf-8'>")
        html_lines.append("<title>Daily Biotech & Science Report ({})</title>".format(self.date_str))
        html_lines.append("<style>")
        html_lines.append("""
             body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }
             .container { max-width: 800px; margin: auto; background: #fff; padding: 20px; }
             h1, h2, h3 { color: #333; }
             .news-item, .paper-item { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; background: #fafafa; }
             .source-date { font-size: 0.9em; color: #666; }
             a { color: #1a0dab; text-decoration: none; }
             a:hover { text-decoration: underline; }
         """)
        html_lines.append("</style>")
        html_lines.append("</head>")
        html_lines.append("<body>")
        html_lines.append("<div class='container'>")
        html_lines.append("<h1>Daily Biotech & Science Report ({})</h1>".format(self.date_str))
        # Biotech Industry News
        html_lines.append("<h2>Biotech Industry & Market News</h2>")
        biotech_news = news_data.get("Biotech Industry", [])
        if biotech_news:
            for item in biotech_news[:6]:
                html_lines.append("<div class='news-item'>")
                html_lines.append("<h3>{}</h3>".format(item['title']))
                html_lines.append("<p class='source-date'><em>{} • {}</em></p>".format(item['source'], item['date']))
                if item.get('summary'):
                    html_lines.append("<p>{}</p>".format(item['summary']))
                html_lines.append("<p><a href='{}' target='_blank'>Read more</a></p>".format(item['link']))
                html_lines.append("</div>")
        else:
            html_lines.append("<p>No recent biotech industry news available today.</p>")
        # Microbiome News
        html_lines.append("<h2>Microbiome & Antimicrobials News</h2>")
        microbiome_news = news_data.get("Microbiome News", [])
        if microbiome_news:
            for item in microbiome_news[:5]:
                html_lines.append("<div class='news-item'>")
                html_lines.append("<h3>{}</h3>".format(item['title']))
                html_lines.append("<p class='source-date'><em>{} • {}</em></p>".format(item['source'], item['date']))
                if item.get('summary'):
                    html_lines.append("<p>{}</p>".format(item['summary']))
                html_lines.append("<p><a href='{}' target='_blank'>Read more</a></p>".format(item['link']))
                html_lines.append("</div>")
        else:
            html_lines.append("<p>No recent microbiome news available today.</p>")
        # Divider for papers
        html_lines.append("<hr>")
        html_lines.append("<h2>Scientific Papers</h2>")
        for category, papers in paper_data.items():
            html_lines.append("<h3>{} Papers</h3>".format(category))
            if papers:
                for paper in papers[:5]:
                    html_lines.append("<div class='paper-item'>")
                    html_lines.append("<h4>{}</h4>".format(paper['title']))
                    html_lines.append("<p class='source-date'><em>{} | {} • {}</em></p>".format(paper['authors'], paper['journal'], paper['date']))
                    abstract = paper.get('abstract', "No abstract available")
                    if len(abstract) > 300:
                        abstract = abstract[:297] + "..."
                    html_lines.append("<p><strong>Abstract:</strong> {}</p>".format(abstract))
                    if paper.get('url'):
                        html_lines.append("<p><a href='{}' target='_blank'>View Paper</a></p>".format(paper['url']))
                    html_lines.append("</div>")
            else:
                html_lines.append("<p>No recent papers on {} available today.</p>".format(category))
        html_lines.append("<hr>")
        html_lines.append("<p><em>Report generated on {}</em></p>".format(self.date_str))
        html_lines.append("</div>")
        html_lines.append("</body>")
        html_lines.append("</html>")
        return "\n".join(html_lines)

    def generate_full_report(self):
        self.console.print("[bold]Generating your daily biotech and science report...[/bold]")
        news_data = {}
        for category in self.news_sources.keys():
            news_data[category] = self.get_all_news(category, days_back=2)
        paper_data = self.search_all_pubmed_categories(days_back=7)
        html_report = self.generate_html_report(news_data, paper_data)
        
        # Save with today's date for archival purposes (optional)
        date_report_path = self.output_dir / f"daily_biotech_report_{self.date_str}.html"
        with open(date_report_path, 'w', encoding='utf-8') as f:
            f.write(html_report)
        
        # Save as index.html (this will be the main file for GitHub Pages)
        index_path = self.output_dir / "index.html"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_report)
        
        self.console.print(f"\n[bold green]Reports saved to:[/bold green] {date_report_path} and {index_path}")
        return index_path

def main():
    tracker = DailyBiotechTrackerHTML()
    tracker.generate_full_report()
    print("Enjoy your coffee while reading your daily science update!")

if __name__ == "__main__":
    main()