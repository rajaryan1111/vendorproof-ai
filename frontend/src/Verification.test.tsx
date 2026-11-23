import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {Verification} from './Verification'

afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('distinguishes an unevaluated supplier from a successful comparison',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>Response.json(url.endsWith('/policy')?{version:0,body:{rules:[],days:0}}:[])))
 render(<Verification sid="synthetic" role="admin" archived={false}/>)
 await screen.findByText('Not evaluated.')
 expect(screen.getByRole('button',{name:'Run verification'}).hasAttribute('disabled')).toBe(true)
})
it('keeps audit access read-only',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>Response.json(url.endsWith('/policy')?{version:1,body:{rules:[],days:0}}:[])))
 render(<Verification sid="synthetic" role="auditor" archived={false}/>)
 await screen.findByText('Current policy v1')
 expect(screen.queryByRole('button',{name:'Run verification'})).toBeNull()
 expect(screen.queryByText('Configure requirements')).toBeNull()
})
