from io import StringIO
from collections import defaultdict
import os

import requests
from bs4 import BeautifulSoup
import pandas as pd


class TrailCounts:
    def __init__(self):
        self.counts = defaultdict(lambda:0)
        self.athletes = []
        # self.session = requests.Session()

    def add_athlete(self, athleteid):
        req = requests.get(f"https://fortcollins.oboztrailexperience.com/AthleteProgress?AthleteID={athleteid}")
        if "Athlete Progress" in req.text:
            bs = BeautifulSoup(req.text, 'html.parser')
            table = bs.find('table', attrs={'class':'data-table-challenge-trail'})
            for tr in table.find_all('tr', {'class':'highlight-on-mouseover'}):
                row = tr.find('i', {'class':'fas'}).attrs['class'][1]
                trailname = tr.find('td', {'class':'trail-data'}).text.strip()
                if 'check' in row:
                    self.counts[trailname] += 1
                else:
                    self.counts[trailname] += 0
            self.athletes.append(athleteid)
            if len(self.athletes) % 20 == 0:
                print(f"Processed {len(self.athletes)} athletes")

    def get_counts(self):
        return self.counts
    
    def get_athletes(self):
        return self.athletes
    
    def to_dataframe(self):
        return pd.DataFrame.from_dict(self.get_counts(), orient='index')

def filter_rewards_limits(table):
    """Pull rewards out of table rows and extract limits if any """
    rewards=  []
    for td in table.find_all('tr', {'class':'highlight-on-mouseover'}):
        row = td.find('i', {'class':'fa-shield-alt'})
        if row:
            rewards.append(row['title'].replace('<b>Promoted Trail</b><br/><p>Complete this trail to ','').replace('</p>',''))
        else:
            rewards.append('')
    
    limits=[]
    for reward in rewards:
        if '(' in reward:
            limits.append(int(reward.split('(')[1].split()[3]))
        else:
            limits.append(0)

    return rewards, limits


def fetch_trail_info_table():
    req = requests.get("https://fortcollins.oboztrailexperience.com/Event")
    bs = BeautifulSoup(req.text, 'html.parser')
    table = bs.find('table', attrs={'class':'data-table-challenge-trail'})
    df = pd.read_html(StringIO(str(table)))[0]

    rewards, limits = filter_rewards_limits(table)
    df.loc[:, 'reward'] = rewards
    df.loc[:, 'limit'] = limits
    df.drop(['Unnamed: 1', 'Unnamed: 7'], axis=1, inplace=True, errors='ignore')
    return df

def update_token():
    pos = requests.post("https://api.terrainscouts.com/Authorize/Token")
    token = f"Bearer {pos.json()['access_token']}"
    return token


def get_athletes():
    token = update_token()
    req = requests.get("https://fortcollins.oboztrailexperience.com/Event/98/AthleteRanking/All",
        headers={
            'Accept': '*/*',
            'Authorization': token,
            'Sec-Fetch-Site': "cross-site",
            'Accept-Language': "en-US,en;q=0.9",
            'Accept-Encoding': "gzip, deflate, br",
            'Sec-Fetch-Mode': "cors",
            'Host': "api.terrainscouts.com",
            'Origin': "https://fortcollins.oboztrailexperience.com",
            'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
            'Connection': "keep-alive",
            'Referer': "https://fortcollins.oboztrailexperience.com/",
            'Sec-Fetch-Dest': "empty",
            }
    )
    data = req.json()
    athletes = [athlete for athlete in data['data'] if athlete['numberOfTrailsComplete'] > 0]
    return athletes


def get_trailcounts(athletes):
    trailcounts = TrailCounts()
    for athlete in athletes:
        trailcounts.add_athlete(athlete['athleteID'])
        # if len(trailcounts.athletes) > 20:
        #     break
    
    tcdf = trailcounts.to_dataframe()
    tcdf.columns = ['count']
    return tcdf


def main():
    df = fetch_trail_info_table()
    athletes = get_athletes()
    tcdf = get_trailcounts(athletes)
    tcdf = tcdf.merge(df, left_index=True, right_on="Trail Name")
    tcdf['%'] = ((tcdf['count'] / tcdf['limit']) * 100) // 1
    tcdf['Trail Name'] = tcdf['Trail Name'].str[:30]
    tcdf['reward'] = tcdf['reward'].str.replace(r'\([^)]*\)', '',regex=True)
    tcdf['reward'] = tcdf['reward'].str.replace("earn a", '',)
    tcdf['reward'] = tcdf['reward'].str.replace("free", '',)
    tcdf['reward'] = tcdf['reward'].str.replace("earn", '',)
    tcdf['reward'] = tcdf['reward'].str.replace("  ", ' ',)
    table = tcdf[['Trail Name', 'count', 'limit', '%', 'reward']].sort_values(['count'],
                                                                        ascending=False).to_markdown(index=False, ).replace("nan", "   ")
    with open("table.md", "wt") as f:
        f.write(table)


if __name__ == "__main__":
    main()
