import pandas as pd

# 各ISAのCSVファイルを読み込み、ISA列を付与
df_x86 = pd.read_csv('x86.csv')
df_x86['ISA'] = 'X86'

df_arm = pd.read_csv('arm.csv')
df_arm['ISA'] = 'AArch64'

df_riscv = pd.read_csv('riscv.csv')
df_riscv['ISA'] = 'RISC-V'

# データを結合し、カラムの並びを整える
df_all = pd.concat([df_x86, df_arm, df_riscv], ignore_index=True)
cols = ['ISA'] + [col for col in df_all.columns if col != 'ISA']
df_all = df_all[cols]

# 結合した結果を保存
df_all.to_csv('all_isa_cpu_features.csv', index=False)
print(f"統合完了: 合計 {len(df_all)} モデルのデータを all_isa_cpu_features.csv に保存しました。")
