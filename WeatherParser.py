import pandas as pd
import numpy as np
from random import randint
import datetime, time
import bs4, requests
from fake_useragent import UserAgent

# словарь с id стран, можно предрасчитать до вызова функции
token = '63466572668a39754a9ddf4c8b3437b0'
link = f'https://www.gismeteo.ru/inform-service/{token}/countries'
p = requests.get(link, headers={'User-Agent': UserAgent().chrome})
soup_countries = bs4.BeautifulSoup(p.text, "html.parser")
countries_dict = {soup_countries.select('item')[i]['n']: soup_countries.select('item')[i]['id'] for i in range(len(soup_countries.select('item')))}

def extract_weather_data(year, month, country='Россия', area=None, city='Москва', countries_dict=countries_dict, token=token):
    """
    Парсинг информации о погоде в городе (city) за определенный год (year) и месяц (month) (кроме ветра и облачности)
    """
    # ищем id желаемой страны
    try:
        country_id = countries_dict[country]
    except:
        raise KeyError('Country is not found')
    
    # если указана область, ищем через нее, иначе без (крупные города можно найти и без указания области)
    if area is not None:
        # ищем id желаемой области
        link = f"https://www.gismeteo.ru/inform-service/{token}/districts/?country={country_id}"
        p = requests.get(link, headers={'User-Agent': UserAgent().chrome})
        soup_areas = bs4.BeautifulSoup(p.text, "html.parser")
        areas_dict = {soup_areas.select('item')[i]['n']: soup_areas.select('item')[i]['id'] for i in range(len(soup_areas.select('item')))}            
        try:
            area_id = areas_dict[area]
        except:
            raise KeyError('Area is not found')
        # ищем id желаемого города
        link = f"https://www.gismeteo.ru/inform-service/{token}/cities/?district={area_id}"
        p = requests.get(link, headers={'User-Agent': UserAgent().chrome})
        soup_city = bs4.BeautifulSoup(p.text, "html.parser")
        city_dict = {soup_city.select('item')[i]['n']: soup_city.select('item')[i]['id'] for i in range(len(soup_city.select('item')))}    
        try:
            city_id = city_dict[city]
        except:
            raise KeyError('City is not found')
    else:
        # ищем id желаемого города
        link = f"https://www.gismeteo.ru/inform-service/{token}/cities/?country={country_id}"
        p = requests.get(link, headers={'User-Agent': UserAgent().chrome})
        soup_city = bs4.BeautifulSoup(p.text, "html.parser")
        city_dict = {soup_city.select('item')[i]['n']: soup_city.select('item')[i]['id'] for i in range(len(soup_city.select('item')))}
        try:
            city_id = city_dict[city]
        except:
            raise KeyError('City is not found')
    
    # месяц должен быть в формате двузначного числа
    if len(str(month)) < 2:
        month = '{:02}'.format(int(month))
        
    # парсим нужный месяц желаемого города  
    link = f'https://www.gismeteo.ru/diary/{city_id}/{year}/{month}/'
    p = requests.get(link, headers={'User-Agent': UserAgent().chrome})
    soup = bs4.BeautifulSoup(p.text, "html.parser")
    
    result_df = pd.DataFrame(columns=['date', 'year', 'month', 'week', 'avg_temperature', 'avg_pressure', 'rain', 'snow', 'storm'])
    len_gismeteo_table = len(soup.select('tr'))
    start = 2 # первые два тега tr не содержат информации о погоде
    
    if soup.title.text == 'Ошибка 404' or len_gismeteo_table < start: # len_gismeteo_table < start бывает в первый день месяца, когда еще нет данных, но страница месяца формально есть
        print(f'Error 404: no data for {year}-{month}')
        return result_df # так удобнее конкатенировать 
    
    date = np.zeros(len_gismeteo_table - start).astype(str)
    rain = np.zeros(len_gismeteo_table - start)
    storm = np.zeros(len_gismeteo_table - start)
    snow = np.zeros(len_gismeteo_table - start)
    avg_atmo_pressures = np.zeros(len_gismeteo_table - start)
    avg_temps = np.zeros(len_gismeteo_table - start)
    
    # преобразуем нужную информацию (температура, давление, атмосферны явления) в датасет. Каждый день имеет два замера
    for i in range(start, len_gismeteo_table):
        cur_string = soup.select('tr')[i].select('td')
        
        # считаем среднюю температуру
        try:
            temp_day = float(cur_string[1].text)
        except:
            temp_day = np.nan
            
        try:
            temp_night = float(cur_string[6].text)
        except:
            temp_night = np.nan           
 
        avg_temp = np.nanmean([temp_day, temp_night])
        avg_temps[i - start] = avg_temp
        
        # считаем среднее давление                            
        try:
            pressure_day = float(cur_string[2].text)
        except:
            pressure_day = np.nan
            
        try:
            pressure_night = float(cur_string[7].text)
        except:
            pressure_night = np.nan
        
        avg_atmo_pressure = np.nanmean([pressure_day, pressure_night])
        avg_atmo_pressures[i - start] = avg_atmo_pressure
        
        # считаем, сколько раз (возможные значения: 0, 1, 2) попало атомсферное явление (возможные значения: rain, storm, snow) в замеры
        try:
            atmo_phenomena_day = soup.select('tr')[i].select('td')[4].img['src'].split('/')[-1][:-4]
        except:
            atmo_phenomena_day = None
            
        try:
            atmo_phenomena_night = soup.select('tr')[i].select('td')[9].img['src'].split('/')[-1][:-4]
        except:
            atmo_phenomena_night = None
       
        for atmo_phenomena in [atmo_phenomena_day, atmo_phenomena_night]:
            if atmo_phenomena is not None:
                if atmo_phenomena == 'rain':
                    rain[i - start] += 1
                elif atmo_phenomena == 'storm':
                    storm[i - start] += 1
                elif atmo_phenomena == 'snow':
                    snow[i - start] += 1
                    
        date[i - start] = f"{year}-{month}-{'{:02}'.format(int(cur_string[0].text))}"
            
    result_df['date'] = pd.to_datetime(date)
    result_df['year'] = year
    result_df['month'] = month
    result_df['week'] = result_df['date'].apply(lambda x: x.isocalendar()[1]) # номер недели (работает так же, как date_part('week', calday) в GP)
    result_df['avg_temperature'] = avg_temps
    result_df['avg_pressure'] = avg_atmo_pressures
    result_df['rain'] = rain
    result_df['snow'] = snow
    result_df['storm'] = storm
    
    # иногда бывают дубли дат в таблице: в одной строке день, в другой ночь (year=2020, month=1, country='Канада', area='Британская Колумбия', city='Ванкувер')
    if np.sum(result_df.duplicated(['date'])) > 0:
        result_df = result_df.groupby(['date', 'year', 'month', 'week']).agg({'avg_temperature': np.nanmean, 'avg_pressure': np.nanmean, 'rain' : np.sum, 'snow' : np.sum,\
                                                                              'storm': np.sum}).reset_index()
    return result_df

def create_weather_df(year_min=2017, year_max=2020, month_min=1, month_max=12, verbose=True, country='Россия', area=None, city='Москва', countries_dict=countries_dict, token=token,
                     sleeping=True, sleep_min=3, sleep_max=10):
    """
    Собираем разные месяца в один датасет
    """
    assert month_min >= 1, 'month_min must be >= 1'
    assert month_max <= 12, 'month_max must be <= 12'
    if month_min > month_max:
        month_min, month_max = month_max, month_min
    if sleeping:
        sleep_min = int(sleep_min)
        sleep_max = int(sleep_max)
        assert sleep_min >= 0, 'int(sleep_min) must be non-negative'
        assert sleep_max >= 0, 'int(sleep_max) must be non-negative'
        if sleep_min > sleep_max:
            sleep_min, sleep_max = sleep_max, sleep_min
        
    weather_df = pd.DataFrame(columns=['date', 'year', 'month', 'week', 'avg_temperature', 'avg_pressure', 'rain', 'snow', 'storm'])
    for year in np.arange(year_min, year_max + 1):
        for month in np.arange(month_min, month_max + 1):
            cur_df = extract_weather_data(year=year, month=month, country=country, area=area, city=city, countries_dict=countries_dict, token=token)
            weather_df = pd.concat([weather_df, cur_df])
            if verbose:
                print(f"{year}-{'{:02}'.format(int(month))} is parsed")
            if sleeping: # на всякий случай
                time.sleep(randint(sleep_min, sleep_max))
    weather_df.reset_index(drop=True, inplace=True)
    return weather_df
