#include <cstdint>
#include <vector>
#include <algorithm>
#include <iostream>
#include <random>
#include <array>
#include <utility>

static std::uint64_t xy2d(std::uint32_t bits, std::uint32_t x, std::uint32_t y){
    std::uint64_t d=0;
    for(std::uint32_t s = 1u<<(bits-1); s>0; s>>=1){
        std::uint32_t rx = (x&s)?1u:0u;
        std::uint32_t ry = (y&s)?1u:0u;
        d += (std::uint64_t)s*(std::uint64_t)s*((3u*rx)^ry);
        if(ry==0){ if(rx==1){ x=s-1-x; y=s-1-y; } std::uint32_t t=x; x=y; y=t; }
    }
    return d;
}

// Hypothesis under test: for aligned square [ox,ox+sz)x[oy,oy+sz), sz=2^k,
// the keys of its cells are exactly [base, base+sz*sz) with base = min over the 4 CORNER cells.
int main(){
    // Part 1: exhaustive over all aligned squares for p=1..8.
    for(std::uint32_t p=1;p<=8;++p){
        std::uint32_t N = 1u<<p;
        for(std::uint32_t k=0;k<=p;++k){
            std::uint32_t sz = 1u<<k;
            for(std::uint32_t ox=0; ox+sz<=N; ox+=sz){
                for(std::uint32_t oy=0; oy+sz<=N; oy+=sz){
                    // brute min/max/set over the square
                    std::uint64_t mn=~0ull, mx=0;
                    std::vector<std::uint64_t> keys;
                    keys.reserve((size_t)sz*sz);
                    for(std::uint32_t x=ox;x<ox+sz;++x)
                        for(std::uint32_t y=oy;y<oy+sz;++y){
                            std::uint64_t d=xy2d(p,x,y); mn=std::min(mn,d); mx=std::max(mx,d); keys.push_back(d);
                        }
                    // corner-min
                    std::uint64_t c0=xy2d(p,ox,oy), c1=xy2d(p,ox+sz-1,oy), c2=xy2d(p,ox,oy+sz-1), c3=xy2d(p,ox+sz-1,oy+sz-1);
                    std::uint64_t cmin=std::min(std::min(c0,c1),std::min(c2,c3));
                    std::uint64_t size=(std::uint64_t)sz*sz;
                    if(cmin!=mn){ std::cout<<"FAIL corner-min p="<<p<<" k="<<k<<" ox="<<ox<<" oy="<<oy<<" cmin="<<cmin<<" mn="<<mn<<"\n"; return 1; }
                    if(mx!=mn+size-1){ std::cout<<"FAIL contiguous range p="<<p<<" k="<<k<<" ox="<<ox<<" oy="<<oy<<"\n"; return 1; }
                    std::sort(keys.begin(),keys.end());
                    for(std::uint64_t i=0;i<size;++i) if(keys[i]!=mn+i){ std::cout<<"FAIL not-a-run p="<<p<<" k="<<k<<"\n"; return 1; }
                }
            }
        }
    }
    std::cout<<"PART1 PASS: aligned square = [corner-min, +4^k) for p=1..8\n";

    // Part 2: decomposition vs brute-force cell enumeration for random integer boxes at p=8.
    std::uint32_t p=8, N=1u<<p;
    std::mt19937 rng(12345);
    std::uniform_int_distribution<std::uint32_t> dc(0,N-1);
    auto range_of_square=[&](std::uint32_t ox,std::uint32_t oy,std::uint32_t k)->std::pair<std::uint64_t,std::uint64_t>{
        std::uint32_t sz=1u<<k;
        std::uint64_t c0=xy2d(p,ox,oy),c1=xy2d(p,ox+sz-1,oy),c2=xy2d(p,ox,oy+sz-1),c3=xy2d(p,ox+sz-1,oy+sz-1);
        std::uint64_t b=std::min(std::min(c0,c1),std::min(c2,c3));
        return {b,(std::uint64_t)sz*sz};
    };
    for(int trial=0; trial<2000; ++trial){
        std::uint32_t x0=dc(rng),x1=dc(rng),y0=dc(rng),y1=dc(rng);
        if(x0>x1)std::swap(x0,x1); if(y0>y1)std::swap(y0,y1);
        // brute: set of keys of cells in box
        std::vector<std::uint64_t> brute;
        for(std::uint32_t x=x0;x<=x1;++x)for(std::uint32_t y=y0;y<=y1;++y)brute.push_back(xy2d(p,x,y));
        std::sort(brute.begin(),brute.end());
        // decompose: recursion collecting ranges
        std::vector<std::pair<std::uint64_t,std::uint64_t>> ranges; // [base,end)
        // iterative stack of (ox,oy,k)
        std::vector<std::array<std::uint32_t,3>> st; st.push_back({{0,0,p}});
        while(!st.empty()){
            auto n=st.back(); st.pop_back();
            std::uint32_t ox=n[0],oy=n[1],k=n[2],sz=1u<<k;
            // disjoint?
            if(ox+sz-1 < x0 || ox > x1 || oy+sz-1 < y0 || oy > y1) continue;
            // contained?
            if(ox>=x0 && ox+sz-1<=x1 && oy>=y0 && oy+sz-1<=y1){
                auto rs=range_of_square(ox,oy,k); ranges.push_back({rs.first,rs.first+rs.second}); continue;
            }
            if(k==0){ auto rs=range_of_square(ox,oy,0); ranges.push_back({rs.first,rs.first+1}); continue; }
            std::uint32_t h=sz>>1;
            st.push_back({{ox,oy,k-1}}); st.push_back({{ox+h,oy,k-1}});
            st.push_back({{ox,oy+h,k-1}}); st.push_back({{ox+h,oy+h,k-1}});
        }
        // expand ranges to key set
        std::vector<std::uint64_t> got;
        for(auto&r:ranges)for(std::uint64_t d=r.first;d<r.second;++d)got.push_back(d);
        std::sort(got.begin(),got.end());
        got.erase(std::unique(got.begin(),got.end()),got.end());
        if(got!=brute){ std::cout<<"FAIL decomp trial "<<trial<<" box="<<x0<<","<<y0<<".."<<x1<<","<<y1<<" got="<<got.size()<<" brute="<<brute.size()<<"\n"; return 1; }
    }
    std::cout<<"PART2 PASS: box decomposition == brute cell enumeration over 2000 random boxes at p=8\n";
    return 0;
}