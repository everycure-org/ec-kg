import polars as pl
import gc
from abc import ABC
from tqdm import tqdm
PRIMEKG_PATH = '/Users/piotrkaniewski/work/ec-kg-analysis/data/primekg'
RTX_PATH = '/Users/piotrkaniewski/work/ec-kg-analysis/data/rtx_kg2'
ROBO_PATH = '/Users/piotrkaniewski/work/ec-kg-analysis/data/robokop'
EC_KG_PATH = '/Users/piotrkaniewski/work/ec-kg-analysis/data/integrated_kg'
INDICATIONS = '/Users/piotrkaniewski/work/ec-kg-analysis/data/ec_indications_list'

KG_DICT = {
    'PrimeKG':PRIMEKG_PATH,
    'RTX-KG2':RTX_PATH,
    'Robokop':ROBO_PATH,
    'EC-KG':EC_KG_PATH,
}

class OffLabelPairSampler(ABC):
    def __init__(self, off_label_path:str, kg_dict):
        self.off_label = pl.read_parquet(off_label_path).filter(pl.col('off_label')).select(pl.col('translator_id').alias('source'),'drug_name','target','disease_name')
        self.kg_dict = KG_DICT

    def intersect_single_kg(self, kg_path):
        kg_df = pl.read_parquet(f'{kg_path}/nodes.norm', columns=['id'])
        df = self.off_label.join(kg_df, left_on='source', right_on='id', how='inner').join(kg_df, left_on='target', right_on='id', how='inner')
        del kg_df
        gc.collect()
        print(df.shape)
        return df

    def intersection_run(self):
        kg_pairs = {}
        for kg, kg_path in tqdm(self.kg_dict.items()):
            kg_pairs[kg] = self.intersect_single_kg(kg_path)
        for i, kg_df in enumerate(kg_pairs.values()):
            if i==0:
                overlapping_df = kg_df
            else:
                overlapping_df = overlapping_df.join(kg_df.select('source','target'), on=['source','target'], how='inner')
        self.pairs = overlapping_df
        del kg_pairs
        gc.collect()
    
    def assign_direct_connection_single_kg(self, pairs, kg, kg_path):
        kg_df = pl.read_parquet(f'{kg_path}/edges.norm', columns=['subject','object']).with_columns(pl.lit(True).alias(f'{kg}_direct_connection')).unique(subset=['subject','object'])
        pairs = pairs.join(kg_df, right_on=['subject','object'], left_on=['source','target'], how='left')
        del kg_df
        gc.collect()
        print(pairs.shape)
        return pairs.fill_null(False)

    def assign_direct_connection(self):
        for kg, kg_path in tqdm(self.kg_dict.items()):
             self.pairs= self.assign_direct_connection_single_kg(self.pairs, kg, kg_path)
        # Combine all direct connection columns to create an overall 'direct_connection' column
        edge_cols = [col for col in self.pairs.columns if col.endswith('_direct_connection')]
        if edge_cols:
            self.pairs = self.pairs.with_columns(
                pl.any_horizontal([pl.col(col) for col in edge_cols]).alias("direct_connection")
            )

    def write_pairs(self, name='off_label_pairs_sop.parquet', only_direct_connection=False):
        n_samples = 200
        if only_direct_connection:
            self.pairs = self.pairs.filter(pl.col('direct_connection')).sample(n_samples)
        else:
            self.pairs = pl.concat([self.pairs.filter(pl.col('direct_connection')).sample(n_samples*0.8), self.pairs.filter(~pl.col('direct_connection')).sample(n_samples*0.2)])
        self.pairs.write_parquet(f'data/{name}')
    
    def run(self):
        print('Running intersection...')
        self.intersection_run()
        print('Assigning direct connection...')
        self.assign_direct_connection()
        print('Writing pairs...')
        self.write_pairs()

def main():
    sampler = OffLabelPairSampler(INDICATIONS, KG_DICT)
    sampler.run()
        

if __name__=='__main__':
    main()