def set_entropy_code(path):
    from algos.fpd_extended_lib.compress import calculate_delta_size
    if ENTROPY_METHOD == "Huffman" or cfg.AUTO_SELECT_METHOD:
        total_deltas = []
        df, _ = bench_utils.read_dataset(path, )
        deltas_by_bits = defaultdict(list)
        for idx in range(len(df)): # List of single idxs
            opt_size, _, delta_list = calculate_delta_size(shape(df.iloc[idx]), True)
            for delta in delta_list[1]:
                #If coordinate not delta_encoded
                if delta != 0 and math.log2(delta) > opt_size:
                    continue
                total_deltas.append(delta)
                deltas_by_bits[opt_size].append(uint_to_ba(delta, opt_size).to01())
        
        delta_freqs = __get_bit_seq_freqs(deltas_by_bits)
        codes = {}
        decode_trees = {}
        for opt_size in delta_freqs:
            codes[opt_size] = __get_entropy_codes(delta_freqs[opt_size])
            decode_trees[opt_size] = decodetree(codes[opt_size])
        cfg.CODES = codes
        cfg.DECODE_TREES = decode_trees




def __get_entropy_codes(frequency_list):
        return util.huffman_code(frequency_list)


def __get_bit_seq_freqs(deltas):
    freq_by_bits = defaultdict(dict)
    for opt_size in deltas: 
        for delta in deltas[opt_size]:  
            delta_len = len(delta)
            if delta in freq_by_bits[delta_len]:
                freq_by_bits[delta_len][delta] += 1
            else:
                freq_by_bits[delta_len][delta] = 1
    return freq_by_bits


def check_optimal_parameter(deltas):
    max_value = math.inf
    best_param = 0
    for i in range(0, 25):
        cfg.ENTROPY_PARAM = i
        tot_sum = 0
        for d in deltas:
            tot_sum += len(golomb_encode(d)[0])
        if tot_sum < max_value:
            best_param = i
            max_value = tot_sum
        tot_sum = 0
    return best_param


if COMPRESS_CHUNK and COMPRESSION_METHOD == "arith":
    from arithmetic_compressor import AECompressor
    from arithmetic_compressor.models import ContextMix_Linear

# create the model
    model = ContextMix_Linear()
    # create an arithmetic coder
    train_arith_model(model, DATASET_PATH, 1000)
    cfg.ARITHMETIC_ENCODER = AECompressor(model, adapt=False)   