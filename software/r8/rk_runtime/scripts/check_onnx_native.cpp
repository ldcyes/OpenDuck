#include <onnxruntime_cxx_api.h>
#include <chrono>
#include <cmath>
#include <algorithm>
#include <iostream>
#include <vector>

int main(int argc,char**argv) {
  try {
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING,"r1-reference-validation");
    Ort::SessionOptions opts;opts.SetIntraOpNumThreads(2);opts.SetInterOpNumThreads(1);
    for(int file=1;file<argc;++file) {
      Ort::Session s(env,argv[file],opts);Ort::AllocatorWithDefaultOptions alloc;
      if(s.GetInputCount()!=1||s.GetOutputCount()!=1)throw std::runtime_error("bad graph arity");
      auto inp=s.GetInputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape();
      auto out=s.GetOutputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape();
      if(inp!=std::vector<int64_t>{1,61}||out!=std::vector<int64_t>{1,14})throw std::runtime_error("bad 61/14 graph");
      auto iname=s.GetInputNameAllocated(0,alloc);auto oname=s.GetOutputNameAllocated(0,alloc);
      const char* ins[]={iname.get()};const char* outs[]={oname.get()};
      auto mem=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
      std::vector<float> v(61,0);std::vector<double> ms;double delta=0;std::vector<float> first;
      for(int iter=0;iter<210;++iter) {
        v[5]=-1;
        for(int j=0;j<3;++j)v[j]=0.02f*std::sin(float(iter+j));
        for(int j=6;j<20;++j)v[j]=0.01f*std::sin(float(iter+j));
        auto tensor=Ort::Value::CreateTensor<float>(mem,v.data(),v.size(),inp.data(),inp.size());
        auto start=std::chrono::steady_clock::now();
        auto result=s.Run(Ort::RunOptions{nullptr},ins,&tensor,1,outs,1);
        double duration=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
        if(iter>=10)ms.push_back(duration);
        const float* a=result[0].GetTensorData<float>();
        for(int j=0;j<14;++j)if(!std::isfinite(a[j]))throw std::runtime_error("nonfinite action");
        if(iter==0)first.assign(a,a+14);
        else for(int j=0;j<14;++j)delta=std::max(delta,double(std::abs(first[j]-a[j])));
      }
      if(delta<1e-8)throw std::runtime_error("constant response to plausible inputs");
      std::sort(ms.begin(),ms.end());
      std::cout << "{\"file\":\"" << argv[file] << "\",\"runtime\":\"" << OrtGetApiBase()->GetVersionString()
                << "\",\"shape\":\"1x61 -> 1x14\",\"finite_inferences\":210,\"p50_ms\":" << ms[100]
                << ",\"p99_ms\":" << ms[198] << ",\"max_ms\":" << ms.back() << ",\"response_variation\":" << delta << "}\n";
    }
  }catch(const std::exception&e) { std::cerr<<e.what()<<"\n";return 2; }
}
