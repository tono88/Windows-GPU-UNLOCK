"""Stock cuBLAS GEMM baseline via installed CUDA DLLs; no driver or firmware changes.

Requires NumPy and a local NVIDIA CUDA Toolkit. This is a numerical GPU workload,
not an unlock, a stability certification or a prediction of LLM token speed.
"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def bind(library, name, args):
    function = getattr(library, name)
    function.argtypes = args
    function.restype = C.c_int
    def call(*values):
        status = function(*values)
        if status:
            raise RuntimeError(name + ' returned status ' + str(status))
    return call


def gpu_snapshot():
    exe = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/nvidia-smi.exe'
    query = 'name,pci.device_id,pci.sub_device_id,driver_version,pstate,temperature.gpu,power.draw,clocks.current.sm,memory.used,memory.free'
    result = subprocess.run([str(exe), '--query-gpu=' + query, '--format=csv,noheader,nounits'],
                            capture_output=True, timeout=15)
    if result.returncode:
        return None
    import csv
    import io
    rows = list(csv.reader(io.StringIO(result.stdout.decode('utf-8-sig').strip())))
    return [dict(zip(query.split(','), [x.strip() for x in row])) for row in rows]


def benchmark(n, samples, launches, cuda_bin):
    import numpy as np
    directory = os.add_dll_directory(str(cuda_bin))
    try:
        driver = C.WinDLL(str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/nvcuda.dll'))
        blas_path = cuda_bin / 'cublas64_11.dll'
        blas = C.WinDLL(str(blas_path))
        pointer, uint64, integer = C.c_void_p, C.c_uint64, C.c_int
        init = bind(driver, 'cuInit', [C.c_uint])
        get_device = bind(driver, 'cuDeviceGet', [C.POINTER(integer), integer])
        create_context = bind(driver, 'cuCtxCreate_v2', [C.POINTER(pointer), C.c_uint, integer])
        destroy_context = bind(driver, 'cuCtxDestroy_v2', [pointer])
        allocate = bind(driver, 'cuMemAlloc_v2', [C.POINTER(uint64), C.c_size_t])
        free = bind(driver, 'cuMemFree_v2', [uint64])
        memory = bind(driver, 'cuMemGetInfo_v2', [C.POINTER(C.c_size_t), C.POINTER(C.c_size_t)])
        upload = bind(driver, 'cuMemcpyHtoD_v2', [uint64, pointer, C.c_size_t])
        download = bind(driver, 'cuMemcpyDtoH_v2', [pointer, uint64, C.c_size_t])
        event_create = bind(driver, 'cuEventCreate', [C.POINTER(pointer), C.c_uint])
        event_record = bind(driver, 'cuEventRecord', [pointer, pointer])
        event_sync = bind(driver, 'cuEventSynchronize', [pointer])
        event_elapsed = bind(driver, 'cuEventElapsedTime', [C.POINTER(C.c_float), pointer, pointer])
        event_destroy = bind(driver, 'cuEventDestroy_v2', [pointer])
        create = bind(blas, 'cublasCreate_v2', [C.POINTER(pointer)])
        destroy = bind(blas, 'cublasDestroy_v2', [pointer])
        math_mode = bind(blas, 'cublasSetMathMode', [pointer, integer])
        gemm = bind(blas, 'cublasGemmEx', [pointer, integer, integer, integer, integer, integer,
                    pointer, pointer, integer, integer, pointer, integer, integer,
                    pointer, pointer, integer, integer, integer, integer])
        init(0)
        device, context, handle = integer(), pointer(), pointer()
        get_device(C.byref(device), 0)
        create_context(C.byref(context), 0, device)
        try:
            create(C.byref(handle))
            try:
                rng = np.random.default_rng(3050330)
                a = np.asfortranarray(rng.integers(-8, 9, (n, n), dtype=np.int16).astype(np.float32) * .125)
                b = np.asfortranarray(rng.integers(-8, 9, (n, n), dtype=np.int16).astype(np.float32) * .125)
                positions = [(int(i), int(j)) for i, j in rng.integers(0, n, (32, 2))]
                expected = np.array([np.dot(a[i, :].astype(np.float64), b[:, j].astype(np.float64))
                                     for i, j in positions])
                results = []
                for name, data_type, compute, pedantic in (
                    ('fp32_pedantic', 0, 69, True), ('fp16_fp32_accumulation', 2, 68, False),
                    ('bf16_fp32_accumulation', 14, 68, False), ('tf32_fp32_accumulation', 0, 77, False)):
                    if data_type == 2:
                        aa, bb = a.astype(np.float16, order='F'), b.astype(np.float16, order='F')
                    elif data_type == 14:
                        # All generated inputs are exactly representable in BF16.
                        aa = np.asfortranarray((a.view(np.uint32) >> 16).astype(np.uint16))
                        bb = np.asfortranarray((b.view(np.uint32) >> 16).astype(np.uint16))
                    else:
                        aa, bb = a, b
                    output = np.empty((n, n), dtype=np.float32, order='F')
                    required = aa.nbytes + bb.nbytes + output.nbytes
                    available, total = C.c_size_t(), C.c_size_t()
                    memory(C.byref(available), C.byref(total))
                    if available.value < required + 256 * 1024**2:
                        raise RuntimeError('Insufficient free VRAM for benchmark plus 256 MiB margin.')
                    allocations, events = [], []
                    try:
                        for array in (aa, bb, output):
                            address = uint64()
                            allocate(C.byref(address), array.nbytes)
                            allocations.append(address)
                        da, db, dc = allocations
                        upload(da, aa.ctypes.data, aa.nbytes)
                        upload(db, bb.ctypes.data, bb.nbytes)
                        alpha, beta = C.c_float(1), C.c_float(0)
                        math_mode(handle, 2 if pedantic else 0)
                        def launch():
                            gemm(handle, 0, 0, n, n, n, C.byref(alpha), pointer(da.value), data_type, n,
                                 pointer(db.value), data_type, n, C.byref(beta), pointer(dc.value), 0, n, compute, -1)
                        for _ in range(3):
                            launch()
                        for _ in range(2):
                            event = pointer()
                            event_create(C.byref(event), 0)
                            events.append(event)
                        start, end = events
                        times = []
                        for _ in range(samples):
                            event_record(start, None)
                            for _ in range(launches):
                                launch()
                            event_record(end, None)
                            event_sync(end)
                            milliseconds = C.c_float()
                            event_elapsed(C.byref(milliseconds), start, end)
                            times.append(milliseconds.value / launches)
                        download(output.ctypes.data, dc, output.nbytes)
                        actual = np.array([output[i, j] for i, j in positions], dtype=np.float64)
                        error = float(np.max(np.abs(actual - expected)))
                        correct = bool(np.isfinite(output).all() and np.allclose(actual, expected, rtol=1e-4, atol=1e-4))
                        if not correct:
                            raise RuntimeError('Numerical validation failed for ' + name)
                        median = statistics.median(times)
                        row = {'mode': name, 'n': n, 'samples_ms': times, 'median_ms': median,
                               'median_tflops': 2 * n**3 / (median * 1e9),
                               'sampled_output_count': len(positions), 'max_sampled_absolute_error': error,
                               'all_outputs_finite': True, 'sampled_validation_passed': correct}
                        results.append(row)
                        print(name, round(row['median_tflops'], 3), 'TFLOP/s; sampled validation passed', flush=True)
                    finally:
                        for event in reversed(events):
                            event_destroy(event)
                        for address in reversed(allocations):
                            free(address)
                with blas_path.open('rb') as stream:
                    dll_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
                return {'seed': 3050330, 'input_domain': 'random integers [-8,8] scaled by 0.125; exactly representable in FP16/BF16/TF32',
                        'numpy_version': np.__version__, 'cublas_dll': blas_path.name,
                        'cublas_sha256': dll_hash,
                        'samples': samples, 'launches_per_sample': launches, 'results': results}
            finally:
                if handle.value:
                    destroy(handle)
        finally:
            destroy_context(context)
    finally:
        directory.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n', type=int, choices=(512, 1024, 2048, 4096), default=2048)
    parser.add_argument('--samples', type=int, choices=range(3, 16), default=7)
    parser.add_argument('--launches', type=int, choices=range(1, 21), default=5)
    parser.add_argument('--cuda-bin', type=Path, default=Path(os.environ.get('CUDA_PATH',
                         r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8')) / 'bin')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('This runner uses installed Windows CUDA DLLs.')
    if args.output.exists():
        parser.error('Choose a new output file; previous results are never overwritten.')
    before = gpu_snapshot()
    if (not before or len(before) != 1 or before[0]['pci.device_id'].lower() != '0x25a010de'
            or before[0]['pci.sub_device_id'].lower() != '0x13dc1043'):
        parser.error('This baseline is restricted to the single observed RTX 3050 Ti Laptop GPU.')
    report = {'schema_version': 1, 'condition': 'stock-boot-no-unlock-attempted',
              'collected_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'before': before, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    report.update(benchmark(args.n, args.samples, args.launches, args.cuda_bin))
    report['after'] = gpu_snapshot()
    report['limits'] = ['one stock Windows session', '32 sampled output checks per mode',
                        'no full random-matrix or model-quality validation',
                        'no controlled unlocked comparison', 'no LLM token-speed measurement',
                        'clock/temperature snapshots are not continuous profiling']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print('Saved', args.output.name)


if __name__ == '__main__':
    main()
